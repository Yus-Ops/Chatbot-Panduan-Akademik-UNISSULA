"""
Backend FastAPI untuk RAG chatbot panduan.

Mengekspos Retriever + Generator sebagai HTTP API streaming (SSE) untuk
frontend Next.js. Komponen dimuat sekali saat start.

Jalankan:
    uvicorn server:app --host 0.0.0.0 --port 8000
(atau:  python -m uvicorn server:app --port 8000)
"""
import json
import os
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.retriever import Retriever
from src.generator import Generator

NOT_FOUND = "Maaf, informasi itu tidak saya temukan di panduan."

print("[server] Memuat retriever & generator...")
retriever = Retriever()
generator = Generator()
print(f"[server] Siap. Panduan aktif: {retriever.guide_name}")

# Proses request bergiliran (serial): hindari menembus rate-limit free tier
# beberapa provider sekaligus. Cukup untuk demo/skripsi.
_llm_lock = threading.Lock()

app = FastAPI(title="Sahabat-RAG API")

# CORS: izinkan frontend (Vercel / localhost) memanggil API ini.
# Set env CORS_ORIGINS="https://app-anda.vercel.app,http://localhost:3000" untuk membatasi.
_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


def _unique_sources(contexts):
    """Daftar sumber unik (judul section + cuplikan), urut sesuai relevansi."""
    seen, items = set(), []
    for c in contexts:
        if c["source"] in seen:
            continue
        seen.add(c["source"])
        items.append({
            "source": c["source"].strip("*# "),
            "snippet": c["text"][:160].replace("\n", " ").strip() + "…",
        })
    return items


def _sse(obj) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@app.get("/")
def root():
    return {"name": "Sahabat-RAG API", "guide": retriever.guide_name,
            "endpoints": ["/health", "POST /chat"]}


@app.get("/health")
def health():
    return {"status": "ok", "guide": retriever.guide_name}


@app.post("/chat")
def chat(req: ChatRequest):
    message = (req.message or "").strip()

    def gen():
        if not message:
            yield _sse({"type": "token", "content": "Silakan ketik pertanyaan."})
            yield _sse({"type": "done"})
            return
        with _llm_lock:                       # proses satu per satu (hemat kuota free tier)
            contexts = retriever.search(message)
            answer = ""
            for token in generator.stream(message, contexts):
                answer += token
                yield _sse({"type": "token", "content": token})
            if contexts and NOT_FOUND not in answer:   # sumber hanya kalau benar menjawab
                yield _sse({"type": "sources", "items": _unique_sources(contexts)})
        yield _sse({"type": "done"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
