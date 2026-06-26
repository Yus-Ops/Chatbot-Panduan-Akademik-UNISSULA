"""Muat index FAISS + embedder, lalu ambil chunk paling relevan untuk pertanyaan.

Dua tahap: (1) e5 ambil kandidat cepat dari FAISS, (2) cross-encoder me-ranking
ulang kandidat secara presisi. Tanpa tahap-2, skor e5 terlalu datar dan jawaban
benar sering kalah dari chunk noise (mis. pertanyaan 'kaprodi ...').
"""
import json
import re

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder

import config
from src.chunking import clean_heading  # fallback bila index lama (tanpa 'crumb')


def expand_query(query: str) -> str:
    """Tambahkan kepanjangan singkatan akademik ke query agar e5 bisa mencocokkan.
    Mis. 'siapa kaprodi teknik informatika' -> '... (ketua program studi)'."""
    low = query.lower()
    # bandingkan case-insensitive: query DAN kunci sama-sama dihuruf-kecilkan,
    # jadi "Kaprodi"/"KAPRODI"/"kaprodi" semuanya cocok, apa pun kapitalisasi kunci.
    extra = [exp for abbr, exp in config.ABBREVIATIONS.items()
             if re.search(rf"\b{re.escape(abbr.lower())}\b", low)]
    return f"{query} ({', '.join(extra)})" if extra else query


class Retriever:
    def __init__(self):
        self.index = faiss.read_index(str(config.INDEX_PATH))
        data = json.loads(config.CHUNKS_PATH.read_text(encoding="utf-8"))
        self.chunks = data["chunks"]
        self.sections = data.get("sections", [])   # isi section utuh, diindeks oleh chunk["sec"]
        self.guide_name = data.get("guide", "")
        self.model = SentenceTransformer(config.EMB_MODEL)
        self.reranker = CrossEncoder(config.RERANK_MODEL) if config.RERANK_MODEL else None

    def _crumb(self, c) -> str:
        """Breadcrumb chunk; fallback ke judul bersih bila index lama tak punya 'crumb'."""
        return c.get("crumb") or clean_heading(c.get("source", ""))

    def search(self, query: str, top_k: int = config.TOP_K):
        qx = expand_query(query)
        # Tahap-1: ambil kandidat dari FAISS (lebih banyak kalau ada reranker).
        n_cand = config.RERANK_CANDIDATES if self.reranker else top_k
        q = self.model.encode(
            [config.EMB_QUERY_PREFIX + qx], normalize_embeddings=True
        ).astype("float32")
        scores, idxs = self.index.search(q, n_cand)
        cand = []
        for score, i in zip(scores[0], idxs[0]):
            if i == -1:
                continue
            c = dict(self.chunks[i])          # salin biar aman menambah field skor
            c["score"] = float(score)
            cand.append(c)
        if not cand:
            return []

        # Tahap-2: cross-encoder rerank. Sertakan BREADCRUMB section + isi (breadcrumb memuat
        # sinyal penting & konteks induk, mis. 'Teknik Informatika') & query yang sudah diekspansi.
        if self.reranker:
            pairs = [[qx, self._crumb(c) + " — " + c["text"]] for c in cand]
            rr = self.reranker.predict(pairs)
            for c, s in zip(cand, rr):
                c["rerank"] = float(s)
            cand.sort(key=lambda c: c["rerank"], reverse=True)
        return self._expand_sections(cand, top_k)

    def _expand_sections(self, cand, top_k):
        """Ganti tiap chunk-hit dengan ISI SECTION UTUH-nya (selama <= MAX_SECTION_CHARS),
        supaya daftar/poin panjang (mis. 12 tujuan FTI) tak hilang sebagian gara-gara cuma
        sebagian chunk yang lolos retrieval. Tiap section utuh hanya dikirim sekali. Section
        raksasa (tabel/lampiran) tetap dikirim per-chunk agar prompt tak meledak.
        Konteks diisi dari peringkat tertinggi sampai CONTEXT_CHAR_BUDGET habis (blok teratas
        selalu disertakan). Urutan hasil mengikuti peringkat rerank; kembalikan
        {"text","source","score"}."""
        out, sent_whole, used = [], set(), 0
        for c in cand:
            if len(out) >= top_k or used >= config.CONTEXT_CHAR_BUDGET:
                break
            sec = c.get("sec")
            section = self.sections[sec] if (sec is not None and sec < len(self.sections)) else None
            whole = bool(section) and len(section["text"]) <= config.MAX_SECTION_CHARS
            if whole and sec in sent_whole:
                continue                      # section ini sudah dikirim utuh -> lewati duplikat
            text = section["text"] if whole else c["text"]
            # hormati anggaran total; tetapi blok teratas selalu masuk walau besar
            if out and used + len(text) > config.CONTEXT_CHAR_BUDGET:
                continue
            if whole:
                sent_whole.add(sec)
            out.append({"text": text, "source": (section["crumb"] if section else self._crumb(c)),
                        "score": c.get("rerank", c.get("score", 0.0))})
            used += len(text)
        return out