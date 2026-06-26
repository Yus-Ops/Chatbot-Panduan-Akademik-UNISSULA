---
title: Chatbot Panduan Akademik Unissula (API)
emoji: 🎓
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Chatbot Panduan Akademik Unissula

RAG chatbot tanya–jawab Panduan Akademik. Jawaban **hanya** dari isi panduan resmi.

> Front matter di atas dipakai Hugging Face Spaces (SDK Docker, port 7860). Aman diabaikan di GitHub.

Pipeline: pertanyaan → ekspansi singkatan → retrieval (e5) → rerank (cross-encoder)
→ **LLM via API** (fallback otomatis antar provider) → jawaban streaming + sumber.

## Arsitektur

```
frontend/  Next.js (UI chat)  ──HTTP streaming (SSE)──►  server.py  FastAPI
                                                          ├─ src/retriever.py  (e5 + reranker, lokal/CPU)
                                                          └─ src/generator.py  (LLM via API + fallback)
```

Generator memanggil LLM lewat **API**, jadi backend **tidak butuh GPU**. Provider
dicoba berurutan dan otomatis pindah saat satu kuotanya habis:

**openmodel.ai → Groq → openagentic.id**

Isi minimal satu API key; provider tanpa key otomatis dilewati.

---

## Menjalankan secara lokal

Butuh: Python 3.11, Node.js 18+, dan minimal satu API key LLM.

### 1) Backend (FastAPI)

```bash
pip install -r requirements.txt

copy .env.example .env        # lalu isi minimal satu API key (lihat di bawah)

python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

Cek: buka <http://localhost:8000/health> → `{"status":"ok", ...}`.

#### Konfigurasi API key (`.env`)

Salin `.env.example` → `.env`, isi key yang kamu punya:

- `GROQ_API_KEY` — dari <https://console.groq.com> (endpoint sudah benar; cukup isi key, opsional `GROQ_MODEL`).
- `OPENMODEL_API_KEY` + `OPENMODEL_BASE_URL` + `OPENMODEL_MODEL` — sesuaikan base_url & nama model dari dashboard openmodel.ai.
- `OPENAGENTIC_API_KEY` + `OPENAGENTIC_BASE_URL` + `OPENAGENTIC_MODEL` — sesuaikan dari dashboard openagentic.id.

> `.env` berisi rahasia dan **tidak ikut ter-commit** (sudah di `.gitignore`).

### 2) Frontend (Next.js)

```bash
cd frontend
npm install
copy .env.local.example .env.local   # default menunjuk ke http://localhost:8000
npm run dev
```

Buka <http://localhost:3000>.

---

## Deploy

Arsitektur: **Frontend (Vercel) → Backend (Hugging Face Space, Docker) → LLM (API)**.
Backend versi API tanpa GPU, jadi cukup **Space CPU gratis** dan dapat URL `https` tetap.

### Backend → Hugging Face Space (Docker)

1. huggingface.co → **New Space** → **SDK: Docker** → Blank.
2. Push repo ini ke Space (HF membaca `Dockerfile` + front matter di `README.md`):
   ```bash
   git remote add space https://huggingface.co/spaces/<user>/<nama-space>
   git push space main
   ```
3. Space → **Settings → Variables and secrets** → tambah **Secrets**:
   `GROQ_API_KEY`, `OPENMODEL_API_KEY`, `OPENMODEL_BASE_URL`, `OPENMODEL_MODEL`,
   `OPENAGENTIC_API_KEY`, `OPENAGENTIC_BASE_URL`, `OPENAGENTIC_MODEL`,
   dan opsional `CORS_ORIGINS` = domain Vercel-mu.
4. Tunggu build → backend hidup di `https://<user>-<nama-space>.hf.space`.
   Cek `https://<user>-<nama-space>.hf.space/health`.

> Space CPU gratis akan "tidur" saat lama tidak dipakai → request pertama ada *cold start*
> (perlu beberapa puluh detik untuk memuat model embedder).

### Frontend → Vercel

1. Import repo ke Vercel, **Root Directory = `frontend`**.
2. Set env `NEXT_PUBLIC_API_URL` = URL Space di atas, lalu **Deploy**.
   (Env `NEXT_PUBLIC_*` dibaca saat *build* → tiap mengubahnya harus **Redeploy**.)

---

## Ingest / ganti panduan

Taruh file panduan baru di `data/guide/`, lalu bangun ulang index:

```bash
python -m src.ingest      # menghasilkan index/index.faiss + index/chunks.json
```

Konversi PDF → Markdown: `python -m scripts.pdf_to_md`.

---

## Catatan

- **Generator butuh internet + API key.** Saat kuota satu provider habis (HTTP 429), otomatis pindah ke provider berikutnya.
- Free tier punya **batas rate** (per menit & per hari). Backend memproses request bergiliran (serial) untuk menghormati limit.
- **Retriever (embedder e5 + reranker) berjalan lokal di CPU** — model diunduh otomatis saat pertama kali dijalankan.
- File model lokal lama (`models/*.gguf`, ~5.7 GB) **tidak dipakai lagi** dan tidak ikut ter-commit; boleh dihapus untuk hemat ruang.
