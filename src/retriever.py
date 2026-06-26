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
from src.chunking import clean_heading


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
        self.guide_name = data.get("guide", "")
        self.model = SentenceTransformer(config.EMB_MODEL)
        self.reranker = CrossEncoder(config.RERANK_MODEL) if config.RERANK_MODEL else None

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
            c = self.chunks[i]
            cand.append({"text": c["text"], "source": c["source"], "score": float(score)})
        if not cand:
            return []

        # Tahap-2: cross-encoder rerank. Sertakan JUDUL section + isi (judul memuat
        # sinyal penting, mis. 'Program Studi Teknik Informatika') & query yang sudah diekspansi.
        if self.reranker:
            pairs = [[qx, clean_heading(c["source"]) + " — " + c["text"]] for c in cand]
            rr = self.reranker.predict(pairs)
            for c, s in zip(cand, rr):
                c["rerank"] = float(s)
            cand.sort(key=lambda c: c["rerank"], reverse=True)
        return cand[:top_k]