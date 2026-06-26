"""Generator jawaban via API LLM, dengan fallback otomatis antar provider.

Mendukung dua protokol per provider (lihat config.PROVIDERS):
- "openai"    : API gaya OpenAI (chat.completions)  -> Groq, openagentic.id
- "anthropic" : API gaya Anthropic (messages)        -> openmodel.ai

Bila satu provider gagal/kuota habis SEBELUM mengeluarkan teks, otomatis lanjut
ke provider berikutnya.
"""
import anthropic
from openai import OpenAI

import config

_INSTRUKSI = (
    "Kamu asisten yang menjawab pertanyaan HANYA berdasarkan KONTEKS dari panduan di bawah. "
    "Jawab dalam Bahasa Indonesia yang akurat dan lengkap. "
    "PERTAHANKAN struktur asli panduan: jika KONTEKS menyajikan informasi sebagai daftar/poin "
    "(mis. visi-misi, tujuan, syarat — dengan butir a/b/c atau 1/2/3), tampilkan jawaban sebagai "
    "daftar berpoin Markdown ('-' atau bernomor) dan salin tiap butir selengkap mungkin sesuai "
    "panduan. JANGAN menggabungkan/meringkas poin-poin itu menjadi satu paragraf. "
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
            protocol = p.get("protocol", "openai")
            if protocol == "anthropic":
                client = anthropic.Anthropic(base_url=p["base_url"], api_key=p["api_key"],
                                             timeout=config.REQUEST_TIMEOUT)
            else:
                client = OpenAI(base_url=p["base_url"], api_key=p["api_key"],
                                timeout=config.REQUEST_TIMEOUT)
            self.providers.append({"name": p["name"], "model": p["model"],
                                   "protocol": protocol, "client": client})
        if self.providers:
            urutan = " -> ".join(f"{pr['name']}({pr['protocol']})" for pr in self.providers)
            print(f"[generator] Provider aktif (urutan fallback): {urutan}")
        else:
            print("[generator] PERINGATAN: tidak ada API key terisi. "
                  "Isi minimal satu di .env (lihat .env.example).")

    def _build_prompt(self, question, contexts):
        blocks = [f"[{i}] (Sumber: {c['source']})\n{c['text']}"
                  for i, c in enumerate(contexts, start=1)]
        konteks = "\n\n".join(blocks) if blocks else "(kosong)"
        return (f"KONTEKS:\n{konteks}\n\nPERTANYAAN: {question}\n\nJAWABAN:")

    def _stream_openai(self, prov, prompt):
        stream = prov["client"].chat.completions.create(
            model=prov["model"],
            messages=[{"role": "system", "content": _INSTRUKSI},
                      {"role": "user", "content": prompt}],
            temperature=config.TEMPERATURE, max_tokens=config.MAX_NEW_TOKENS, stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta

    def _stream_anthropic(self, prov, prompt):
        # Anthropic: system terpisah dari messages. text_stream HANYA mengeluarkan teks
        # jawaban (blok "thinking" pada model reasoning otomatis dilewati).
        with prov["client"].messages.stream(
            model=prov["model"], max_tokens=config.MAX_NEW_TOKENS,
            temperature=config.TEMPERATURE, system=_INSTRUKSI,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text

    def stream(self, question, contexts):
        if not contexts:                      # tak ada chunk relevan -> jawab pasti, tanpa LLM
            yield _NOT_FOUND
            return
        if not self.providers:                # belum ada API key dikonfigurasi
            yield "Maaf, layanan AI belum dikonfigurasi (API key kosong). Lihat .env.example."
            return

        prompt = self._build_prompt(question, contexts)
        for prov in self.providers:
            sudah_keluar = False              # apakah sudah sempat streaming token dari provider ini
            try:
                gen = (self._stream_anthropic(prov, prompt) if prov["protocol"] == "anthropic"
                       else self._stream_openai(prov, prompt))
                for delta in gen:
                    if delta:
                        sudah_keluar = True
                        yield delta
            except Exception as e:
                print(f"[generator] provider '{prov['name']}' gagal: {e}")
                if sudah_keluar:
                    # Sudah terlanjur kirim sebagian -> jangan pindah provider (hindari dobel).
                    return
                continue                      # belum ada token (mis. 429) -> coba berikutnya
            if sudah_keluar:
                return                        # sukses -> selesai
            print(f"[generator] provider '{prov['name']}' tidak mengembalikan teks -> coba berikutnya")

        yield "Maaf, semua layanan AI sedang sibuk atau kuotanya habis. Coba lagi nanti."
