"""Konversi panduan -> Markdown pakai Docling (auto-deteksi PDF/DOCX/dll).
Pakai: python scripts/pdf_to_md.py panduan-2026.pdf data/guide/panduan-2026.md"""
import sys, pathlib
from docling.document_converter import DocumentConverter

src, dst = sys.argv[1], sys.argv[2]
converter = DocumentConverter()
result = converter.convert(src)                 # path atau URL; format dideteksi otomatis
md = result.document.export_to_markdown()
pathlib.Path(dst).write_text(md, encoding="utf-8")
print(f"Tersimpan: {dst} ({len(md)} karakter)")