"""Pecah dokumen panduan jadi chunk, sebisa mungkin mengikuti struktur heading."""
import re
from pathlib import Path

import config


def clean_heading(source: str) -> str:
    """Buang markup markdown (**, #, >) dari judul heading agar bisa dibandingkan & di-embed."""
    return re.sub(r"[*#>]", "", source).strip()


_NUM_PREFIX = re.compile(r"^(\d+(?:\.\d+)*)")

def heading_depth(title_clean: str, hashes: int) -> int:
    """Kedalaman heading untuk menyusun breadcrumb.
    Pakai NOMOR section bila ada ('3.2.2.4' -> 4, '1.3' -> 2), karena level '#' hasil
    konversi PDF sering tidak konsisten (mis. saudara Visi/Misi/Tujuan beda level).
    Tanpa nomor (mis. 'Tujuan :', 'BAB II'): pakai jumlah tanda '#'."""
    m = _NUM_PREFIX.match(title_clean)
    return m.group(1).count(".") + 1 if m else hashes


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
    Kembalikan (chunks, sections).
    - chunks  : list {"id","text","source","crumb","sec"} -> unit RETRIEVAL (window kecil,
                presisi embedding). 'sec' menunjuk ke indeks pada `sections`.
    - sections: list {"title","crumb","text"} per-heading -> unit JAWABAN (isi section UTUH).
                Retriever memakai ini untuk mengirim section penuh ke LLM agar daftar/poin
                (mis. 12 tujuan FTI) tidak terpotong antar-chunk.

    'crumb' = breadcrumb heading (induk > ... > judul). Berguna karena banyak sub-judul
    ambigu kalau berdiri sendiri (mis. "Tujuan :" FTI vs "3.2.2.4 Tujuan" prodi); breadcrumb
    memberi konteks induk ke embedder/reranker DAN ke LLM saat menyusun jawaban.
    Kalau tak ada heading markdown sama sekali: window polos, tiap window jadi section sendiri.
    """
    text = load_text(path)
    text = re.sub(r"!\[\]\([^)]*\)", "", text)   # buang ref gambar marker-pdf (mis. ![](_page_7_Picture.jpeg))
    text = text.replace("<br>", " ")             # <br> dalam sel tabel -> spasi
    chunks, sections = [], []

    heading_re = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
    matches = list(heading_re.finditer(text))

    if matches:
        stack = []   # [(depth, judul_bersih)] -> menyusun breadcrumb mengikuti kedalaman heading
        for idx, m in enumerate(matches):
            title = m.group(2).strip()
            ctitle = clean_heading(title)
            depth = heading_depth(ctitle, len(m.group(1)))
            while stack and stack[-1][0] >= depth:   # keluar dari heading sederajat/lebih dalam
                stack.pop()
            stack.append((depth, ctitle))
            crumb = " > ".join(t for _, t in stack)

            start = m.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            sections.append({"title": title, "crumb": crumb, "text": body})
            for piece in _window(body, config.CHUNK_SIZE, config.CHUNK_OVERLAP):
                chunks.append({"text": piece, "source": title, "crumb": crumb, "sec": idx})
    else:
        for i, piece in enumerate(_window(text, config.CHUNK_SIZE, config.CHUNK_OVERLAP)):
            label = f"Bagian {i + 1}"
            chunks.append({"text": piece, "source": label, "crumb": label, "sec": i})
            sections.append({"title": label, "crumb": label, "text": piece})

    for i, c in enumerate(chunks):
        c["id"] = i
    return chunks, sections