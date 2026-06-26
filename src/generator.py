"""Generator jawaban via API LLM, dengan fallback otomatis antar provider.

Bangun prompt grounded dari konteks panduan, lalu stream jawaban dari provider
pertama yang tersedia (urutan ada di config.PROVIDERS). Bila satu provider gagal
atau kuotanya habis (mis. HTTP 429 saat awal request), otomatis lanjut ke
provider berikutnya. Semua provider diasumsikan OpenAI-compatible.
"""
from openai import OpenAI

import config

_INSTRUKSI = (
    "Kamu asisten yang menjawab pertanyaan HANYA berdasarkan KONTEKS dari panduan di bawah. "
    "Jawab dalam Bahasa Indonesia, ringkas dan akurat. "
    "Bila KONTEKS memuat aturan/ketentuan umum (mis. berlaku untuk semua program sarjana/S1), "
    "terapkan untuk menjawab pertanyaan tentang program studi S1 tertentu (mis. Teknik Informatika). "
    "Jika jawabannya benar-benar tidak ada di KONTEKS, katakan: "
    "\"Maaf, informasi itu tidak saya temukan di panduan.\" "
    "Jangan mengarang fakta yang tidak ada di KONTEKS."
)

_NOT_FOUND = "Maaf, informasi itu tidak saya temukan di panduan."


class Generator:
    def __init__(self):
        # Siapkan client untuk tiap provider yang API key-nya terisi; sisanya dilewati.
        self.providers = []
        for p in config.PROVIDERS:
            if not p.get("api_key"):
                continue
            self.providers.append({
                "name": p["name"],
                "model": p["model"],
                "client": OpenAI(
                    base_url=p["base_url"],
                    api_key=p["api_key"],
                    timeout=config.REQUEST_TIMEOUT,
                ),
            })
        if self.providers:
            urutan = " -> ".join(pr["name"] for pr in self.providers)
            print(f"[generator] Provider aktif (urutan fallback): {urutan}")
        else:
            print("[generator] PERINGATAN: tidak ada API key terisi. "
                  "Isi minimal satu di .env (lihat .env.example).")

    def _build_prompt(self, question, contexts):
        blocks = [f"[{i}] (Sumber: {c['source']})\n{c['text']}"
                  for i, c in enumerate(contexts, start=1)]
        konteks = "\n\n".join(blocks) if blocks else "(kosong)"
        return (f"KONTEKS:\n{konteks}\n\n"
                f"PERTANYAAN: {question}\n\nJAWABAN:")

    def stream(self, question, contexts):
        if not contexts:                      # tak ada chunk relevan -> jawab pasti, tanpa LLM
            yield _NOT_FOUND
            return
        if not self.providers:                # belum ada API key dikonfigurasi
            yield "Maaf, layanan AI belum dikonfigurasi (API key kosong). Lihat .env.example."
            return

        # Beda dgn Gemma lokal (tak punya system role), API mendukung system role ->
        # instruksi ditaruh terpisah supaya grounding lebih kuat.
        messages = [
            {"role": "system", "content": _INSTRUKSI},
            {"role": "user", "content": self._build_prompt(question, contexts)},
        ]

        for prov in self.providers:
            sudah_keluar = False              # apakah sudah sempat streaming token dari provider ini
            try:
                stream = prov["client"].chat.completions.create(
                    model=prov["model"],
                    messages=messages,
                    temperature=config.TEMPERATURE,
                    max_tokens=config.MAX_NEW_TOKENS,
                    stream=True,
                )
                for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        sudah_keluar = True
                        yield delta
            except Exception as e:
                print(f"[generator] provider '{prov['name']}' gagal: {e}")
                if sudah_keluar:
                    # Sudah terlanjur mengirim sebagian jawaban -> JANGAN pindah provider
                    # (akan menghasilkan jawaban dobel/berantakan). Hentikan saja.
                    return
                # Belum ada token (mis. kuota habis 429 di awal) -> aman lanjut ke berikutnya.
                continue

            if sudah_keluar:
                return                        # sukses -> selesai
            # Stream selesai tanpa teks sama sekali -> anggap gagal, coba provider berikutnya.
            print(f"[generator] provider '{prov['name']}' tidak mengembalikan teks -> coba berikutnya")

        yield "Maaf, semua layanan AI sedang sibuk atau kuotanya habis. Coba lagi nanti."
