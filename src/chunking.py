"""Pecah dokumen panduan jadi chunk, sebisa mungkin mengikuti struktur heading."""
import re
from pathlib import Path

import config


def clean_heading(source: str) -> str:
    """Buang markup markdown (**, #, >) dari judul heading agar bisa dibandingkan & di-embed."""
    return re.sub(r"[*#>]", "", source).strip()


def load_text(path: Path) -> str:
    """Baca panduan. Dukung .md/.txt langsung; .pdf via pypdf."""
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        parts = []
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            parts.append(f"[Halaman {i}]\n{text}")
        return "\n\n".join(parts)
    raise ValueError(f"Format tidak didukung: {suffix} (pakai .md/.txt/.pdf)")


def _window(text: str, size: int, overlap: int):
    """Sliding window berbasis karakter dengan overlap."""
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + size].strip())
        start += size - overlap
    return [c for c in chunks if c]

def drop_noise(chunks):
    """Buang front matter (judul di SKIP_SECTIONS) + pecahan tabel kosong (low-density)."""
    def keep(c):
        if clean_heading(c["source"]).lower() in config.SKIP_SECTIONS:
            return False                       # daftar isi, kata pengantar, dll
        t = c["text"]
        if not t or sum(ch.isalnum() for ch in t) / len(t) < config.MIN_ALNUM_RATIO:
            return False                       # skeleton tabel '|---|--|' tanpa isi nyata
        return True
    kept = [c for c in chunks if keep(c)]
    for i, c in enumerate(kept):      # nomori ulang
        c["id"] = i
    return kept

def chunk_document(path: Path):
    """
    Kembalikan list dict {"id", "text", "source"}.
    Kalau ada heading markdown (#, ##, ...): pecah per-section dulu lalu window,
    'source' = judul heading. Kalau tidak: window polos.
    """
    text = load_text(path)
    text = re.sub(r"!\[\]\([^)]*\)", "", text)   # buang ref gambar marker-pdf (mis. ![](_page_7_Picture.jpeg))
    text = text.replace("<br>", " ")             # <br> dalam sel tabel -> spasi
    chunks = []

    heading_re = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)
    matches = list(heading_re.finditer(text))

    if matches:
        for idx, m in enumerate(matches):
            title = m.group(1).strip()
            start = m.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            for piece in _window(text[start:end], config.CHUNK_SIZE, config.CHUNK_OVERLAP):
                chunks.append({"text": piece, "source": title})
    else:
        for i, piece in enumerate(_window(text, config.CHUNK_SIZE, config.CHUNK_OVERLAP)):
            chunks.append({"text": piece, "source": f"Bagian {i + 1}"})

    for i, c in enumerate(chunks):
        c["id"] = i
    return chunks