# syntax=docker/dockerfile:1
#
# Backend RAG chatbot (FastAPI) — image untuk Hugging Face Spaces (SDK: docker).
# Generasi LLM lewat API (OpenAI-compatible) => TANPA GPU. Yang berjalan lokal di
# CPU hanya retrieval (embedder e5 + cross-encoder reranker). Listen di port 7860.

FROM python:3.11-slim

# Lingkungan Python yang bersih untuk container
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# HF Spaces menjalankan container sebagai user non-root (uid 1000).
# Buat user + arahkan cache model ke folder yang writable olehnya.
RUN useradd --create-home --uid 1000 appuser
ENV HOME=/home/appuser \
    HF_HOME=/home/appuser/.cache/huggingface

WORKDIR /app

# Torch versi CPU-only dulu (jauh lebih kecil daripada default yang membawa CUDA).
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# Dependency lain (layer cache: tidak re-install saat hanya kode yang berubah).
COPY requirements.txt .
RUN pip install -r requirements.txt

# Kode aplikasi + index FAISS. frontend/, models/, .git, dll. dikecualikan via .dockerignore.
COPY . .

# Beri kepemilikan ke user non-root, lalu beralih ke user tersebut.
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 7860

# Health check via endpoint /health (berguna saat dijalankan di Docker host mana pun).
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:7860/health').status==200 else 1)"

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7860"]
