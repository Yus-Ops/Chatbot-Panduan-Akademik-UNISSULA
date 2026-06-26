"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getHealth, streamChat, type Source } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
}

const EXAMPLES = [
  "Siapa Kaprodi Teknik Informatika?",
  "Apa visi misi Fakultas Teknologi Industri?",
  "Syarat mengambil Tugas Akhir apa saja?",
  "Apa saja program studi di FTI?",
];

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [guide, setGuide] = useState<string | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  function checkHealth() {
    setOnline(null);
    getHealth()
      .then((h) => {
        setGuide(h.guide);
        setOnline(true);
      })
      .catch(() => setOnline(false));
  }

  useEffect(() => {
    checkHealth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  function updateLast(fn: (m: Message) => Message) {
    setMessages((msgs) => {
      const copy = [...msgs];
      copy[copy.length - 1] = fn(copy[copy.length - 1]);
      return copy;
    });
  }

  async function send(text: string) {
    const q = text.trim();
    if (!q || streaming) return;
    setInput("");
    if (taRef.current) taRef.current.style.height = "auto";
    setMessages((m) => [
      ...m,
      { role: "user", content: q },
      { role: "assistant", content: "" },
    ]);
    setStreaming(true);

    const ac = new AbortController();
    abortRef.current = ac;
    try {
      await streamChat(
        q,
        {
          onToken: (t) => updateLast((m) => ({ ...m, content: m.content + t })),
          onSources: (s) => updateLast((m) => ({ ...m, sources: s })),
          onDone: () => {},
        },
        ac.signal
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        updateLast((m) => ({
          ...m,
          content:
            m.content ||
            "⚠️ Gagal menghubungi server. Pastikan backend berjalan dan `NEXT_PUBLIC_API_URL` benar.",
        }));
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  function stop() {
    abortRef.current?.abort();
    setStreaming(false);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  function autoGrow(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
  }

  const empty = messages.length === 0;

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b border-brand-200/60 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80">
        <div className="mx-auto flex max-w-3xl items-center gap-3 px-4 py-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-lg font-bold text-white shadow-glow">
            U
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-base font-semibold leading-tight">
              Chatbot Panduan Akademik Unissula
            </h1>
            <p className="flex items-center gap-1.5 truncate text-xs text-slate-500 dark:text-slate-400">
              <span
                className={`inline-block h-2 w-2 rounded-full ${
                  online === false
                    ? "bg-red-500"
                    : online
                      ? "bg-brand-500"
                      : "bg-slate-400"
                }`}
              />
              {online === false
                ? "Server tidak terhubung"
                : guide
                  ? `Sumber: ${guide}`
                  : "Menghubungkan…"}
            </p>
          </div>
        </div>
      </header>

      {/* Daftar pesan */}
      <main ref={scrollRef} className="scroll-area flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-4 py-6">
          {empty ? (
            <div className="mt-10 flex flex-col items-center text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 text-2xl font-bold text-white shadow-glow">
                U
              </div>
              <h2 className="text-xl font-semibold">
                Selamat datang 👋
              </h2>
              <p className="mt-2 max-w-md text-sm text-slate-500 dark:text-slate-400">
                Tanya apa saja tentang Panduan Akademik. Jawaban hanya
                berdasarkan isi panduan resmi.
              </p>
              <div className="mt-6 grid w-full gap-2 sm:grid-cols-2">
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex}
                    onClick={() => send(ex)}
                    className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-700 transition hover:border-brand-500 hover:bg-brand-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:border-brand-500 dark:hover:bg-slate-700"
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-5">
              {messages.map((m, i) => (
                <MessageBubble
                  key={i}
                  message={m}
                  loading={
                    streaming &&
                    i === messages.length - 1 &&
                    m.role === "assistant" &&
                    m.content === ""
                  }
                />
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Input */}
      <footer className="border-t border-brand-200/60 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80">
        <div className="mx-auto max-w-3xl px-4 py-3">
          <div className="flex items-end gap-2 rounded-2xl border border-slate-300 bg-white p-2 shadow-sm focus-within:border-brand-500 dark:border-slate-700 dark:bg-slate-800">
            <textarea
              ref={taRef}
              value={input}
              onChange={autoGrow}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="Ketik pertanyaan… (Enter kirim, Shift+Enter baris baru)"
              className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-slate-400"
            />
            {streaming ? (
              <button
                onClick={stop}
                title="Hentikan"
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-200 text-slate-700 transition hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-200"
              >
                <span className="h-3 w-3 rounded-[3px] bg-current" />
              </button>
            ) : (
              <button
                onClick={() => send(input)}
                disabled={!input.trim()}
                title="Kirim"
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 2 11 13" />
                  <path d="M22 2 15 22l-4-9-9-4 20-7Z" />
                </svg>
              </button>
            )}
          </div>
          <p className="mt-1.5 text-center text-[11px] text-slate-400">
            Jawaban dihasilkan AI dari isi panduan — selalu verifikasi info penting.
          </p>
        </div>
      </footer>

    </div>
  );
}

function MessageBubble({
  message,
  loading,
}: {
  message: Message;
  loading: boolean;
}) {
  const isUser = message.role === "user";
  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm font-semibold ${
          isUser
            ? "bg-slate-700 text-white dark:bg-slate-600"
            : "bg-gradient-to-br from-brand-500 to-brand-700 text-white"
        }`}
      >
        {isUser ? "A" : "U"}
      </div>
      <div className={`min-w-0 max-w-[85%] ${isUser ? "items-end" : ""}`}>
        <div
          className={`rounded-2xl px-4 py-2.5 text-sm shadow-sm ${
            isUser
              ? "bg-brand-200 text-slate-900"
              : "border border-slate-200 bg-white text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
          }`}
        >
          {loading ? (
            <span className="typing text-slate-400">
              <span />
              <span />
              <span />
            </span>
          ) : isUser ? (
            <span className="whitespace-pre-wrap">{message.content}</span>
          ) : (
            <div className="md">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {message.sources && message.sources.length > 0 && (
          <details className="mt-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-slate-700 dark:bg-slate-800/60">
            <summary className="cursor-pointer select-none font-medium text-slate-600 dark:text-slate-300">
              📚 {message.sources.length} sumber dari panduan
            </summary>
            <ul className="mt-2 flex flex-col gap-2">
              {message.sources.map((s, i) => (
                <li key={i} className="text-slate-500 dark:text-slate-400">
                  <span className="font-medium text-slate-700 dark:text-slate-200">
                    {s.source}
                  </span>
                  <span className="block opacity-80">{s.snippet}</span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </div>
  );
}
