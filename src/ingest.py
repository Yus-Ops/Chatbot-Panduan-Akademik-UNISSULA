"""
Bangun index FAISS dari panduan TERBARU.
Dijalankan di CI tiap ada commit panduan baru, atau lokal:  python -m src.ingest
Output: index/index.faiss + index/chunks.json
"""
import json
import sys

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

import config
from src.chunking import chunk_document, drop_noise

def latest_guide():
    files = sorted(config.GUIDE_DIR.glob(config.GUIDE_GLOB))
    if not files:
        sys.exit(f"Tidak ada panduan di {config.GUIDE_DIR} (pola: {config.GUIDE_GLOB})")
    return files[-1]  # 'panduan-2026...' > 'panduan-2025...' secara leksikal


def build():
    guide = latest_guide()
    print(f"[ingest] Memproses: {guide.name}")

    chunks, sections = chunk_document(guide)
    print(f"[ingest] {len(chunks)} chunk, {len(sections)} section dibuat")

    chunks = drop_noise(chunks)
    print(f"[ingest] {len(chunks)} chunk dipakai (front matter dibuang)")

    model = SentenceTransformer(config.EMB_MODEL)
    # Embed BREADCRUMB heading + isi: query spt "visi misi" cocok walau kata itu cuma ada di
    # heading, dan breadcrumb (induk > anak) bantu membedakan sub-judul ambigu antar-section.
    passages = [config.EMB_PASSAGE_PREFIX + c["crumb"] + " — " + c["text"]
                for c in chunks]
    emb = model.encode(passages, normalize_embeddings=True, show_progress_bar=True)
    emb = np.asarray(emb, dtype="float32")

    index = faiss.IndexFlatIP(emb.shape[1])  # IP + vektor ternormalisasi = cosine
    index.add(emb)

    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(config.INDEX_PATH))
    config.CHUNKS_PATH.write_text(
        json.dumps({"guide": guide.name, "chunks": chunks, "sections": sections},
                   ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[ingest] Index disimpan -> {config.INDEX_PATH}")


if __name__ == "__main__":
    build()