"""Konfigurasi terpusat untuk RAG chatbot panduan akademik."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")   # baca API key & override lain dari .env (kalau ada)


# --- Generator (LLM via API, dengan fallback berurutan) ---
# Provider dicoba dari ATAS ke BAWAH. Yang API key-nya kosong otomatis dilewati.
# Saat satu provider gagal/kuota habis, generator lanjut ke provider berikutnya.
#
# "protocol" menentukan SDK/format yang dipakai:
#   - "openai"    -> API gaya OpenAI (chat.completions)  : Groq, openagentic.id
#   - "anthropic" -> API gaya Anthropic (messages)        : openmodel.ai
# base_url, model, dan API key diisi lewat .env (lihat .env.example).
# Urutan bebas diubah; Groq ditaruh pertama karena paling cepat & andal.
PROVIDERS = [
    {
        "name": "groq",
        "protocol": "openai",
        "base_url": os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        "model":    os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "api_key":  os.environ.get("GROQ_API_KEY", ""),
    },
    {
        "name": "openagentic.id",
        "protocol": "openai",
        "base_url": os.environ.get("OPENAGENTIC_BASE_URL", "https://openagentic.id/api/v1"),
        "model":    os.environ.get("OPENAGENTIC_MODEL", "claude-sonnet-4.5"),
        "api_key":  os.environ.get("OPENAGENTIC_API_KEY", ""),
    },
    {
        "name": "openmodel.ai",
        "protocol": "anthropic",  # API gaya Anthropic; base_url TANPA /v1
        "base_url": os.environ.get("OPENMODEL_BASE_URL", "https://api.openmodel.ai"),
        "model":    os.environ.get("OPENMODEL_MODEL", "deepseek-v4-flash"),
        "api_key":  os.environ.get("OPENMODEL_API_KEY", ""),
    },
]

REQUEST_TIMEOUT = 60       # detik: batas tunggu per request ke API sebelum dianggap gagal
MAX_NEW_TOKENS = 3000      # batas panjang jawaban (naikkan lagi bila masih kepotong)
TEMPERATURE = 0.3          # rendah -> lebih patuh konteks, lebih sedikit mengarang

# --- Embedder (retrieval, tahap-1 / kandidat) ---
EMB_MODEL = "intfloat/multilingual-e5-small"
EMB_QUERY_PREFIX = "query: "      # e5 WAJIB prefix ini untuk query
EMB_PASSAGE_PREFIX = "passage: "  # ...dan ini untuk dokumen

# --- Reranker (tahap-2 / cross-encoder) ---
# e5-small skornya datar (semua ~0.86) -> jawaban benar sering tenggelam di antara noise.
# Cross-encoder me-ranking ulang kandidat dgn jauh lebih presisi. Kosongkan ("") utk nonaktif.
RERANK_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
RERANK_CANDIDATES = 24     # ambil sebanyak ini dari e5, lalu cross-encoder pilih TOP_K terbaik

# --- Chunking ---
CHUNK_SIZE = 900           # ~karakter per chunk
CHUNK_OVERLAP = 150
MIN_ALNUM_RATIO = 0.15     # buang chunk skeleton tabel: rasio alfanumerik < ini (mis. '|---|--|')

# --- Retrieval ---
TOP_K = 8                  # jumlah blok konteks dikirim ke LLM (lebih sedikit -> prompt lebih ringkas)

# Saat sebuah chunk terpilih, kirim SELURUH isi section-nya ke LLM (bukan cuma potongan
# window) selama ukurannya <= ini. Tujuannya: daftar/poin panjang (mis. 12 tujuan FTI)
# sering terpecah jadi beberapa chunk; kalau cuma sebagian chunk yang lolos retrieval,
# jawaban jadi kepotong (cuma 4 poin). Dengan mengirim section utuh, semua poin ikut.
# Section yang LEBIH besar dari ini (tabel kurikulum, lampiran) tetap dikirim per-chunk
# supaya prompt tidak meledak. ~4500 char cukup memuat section visi/misi/tujuan terpanjang.
MAX_SECTION_CHARS = 4500

# Anggaran total karakter konteks yang dikirim ke LLM (lintas semua blok). Mengirim section
# utuh bisa menggelembungkan prompt; batas ini menjaga biaya token & kuota harian tetap wajar
# (Groq free tier dibatasi token/hari). Blok diisi dari peringkat tertinggi sampai anggaran
# habis; blok teratas selalu disertakan walau besar. ~6000 char cukup memuat 1 daftar penuh
# (mis. 12 tujuan FTI ~2700 char) plus beberapa blok pendukung.
CONTEXT_CHAR_BUDGET = 6000

# Ekspansi singkatan: e5-small tak paham akronim akademik Indonesia (mis. "kaprodi"),
# jadi query "kaprodi teknik informatika" gagal menemukan chunk "Ketua : ...".
# Singkatan yang muncul di pertanyaan ditambahkan bentuk panjangnya sebelum di-embed.
# Tulis kunci HURUF KECIL (pencocokan case-insensitive, jadi "Kaprodi"/"KAPRODI" tetap kena).
# Hanya singkatan yang TIDAK ambigu (hindari "TI" = Teknik Industri/Informatika).
ABBREVIATIONS = {
    "kaprodi": "ketua program studi",
    "sekprodi": "sekretaris program studi",
    "kajur": "ketua jurusan",
    "sekjur": "sekretaris jurusan",
    "wadek": "wakil dekan",
    "kalab": "kepala laboratorium",
    "ka lab": "kepala laboratorium",
    "kaur": "kepala urusan",
    "prodi": "program studi",
    "kp": "kerja praktek",
    "ta": "tugas akhir",
    "sks": "satuan kredit semester",
    "ukt": "uang kuliah tunggal",
    "ipk": "indeks prestasi kumulatif",
    "krs": "kartu rencana studi",
    "fti": "fakultas teknologi industri",
    # Sinonim FRASA (bukan singkatan): bantu cocokkan istilah pertanyaan dgn istilah
    # di panduan. Mis. "beban studi prodi" -> panduan menulis "beban akademik ... SKS"
    # untuk program S1 (bukan per-prodi), jadi tambahkan kata kuncinya.
    "beban studi": "beban akademik jumlah total sks untuk lulus program sarjana s1",
    "total sks": "beban akademik jumlah sks untuk lulus program sarjana s1",
}

# --- Data & index ---
GUIDE_DIR = ROOT / "data" / "guide"
GUIDE_GLOB = "[Pp]anduan-*.*" # case-insensitive: glob di Linux (CI) sensitif huruf besar/kecil
INDEX_DIR = ROOT / "index"
INDEX_PATH = INDEX_DIR / "index.faiss"
CHUNKS_PATH = INDEX_DIR / "chunks.json"

# Bagian non-konten yang dilewati saat ingest (front matter)
SKIP_SECTIONS = {"kata pengantar", "daftar isi", "daftar tabel", "daftar gambar",
                 "sambutan", "lembar pengesahan"}
