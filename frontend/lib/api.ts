// Klien API ke backend FastAPI (streaming SSE).
export interface Source {
  source: string;
  snippet: string;
}

export interface StreamCallbacks {
  onToken: (t: string) => void;
  onSources: (s: Source[]) => void;
  onDone: () => void;
}

const DEFAULT_API =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";
const LS_KEY = "backendUrl";

/** URL backend efektif. Prioritas: override di browser (localStorage) > env build > default. */
export function getApiUrl(): string {
  if (typeof window !== "undefined") {
    const saved = window.localStorage.getItem(LS_KEY);
    if (saved && saved.trim()) return saved.trim().replace(/\/$/, "");
  }
  return DEFAULT_API;
}

/** Simpan (atau hapus, jika kosong) override URL backend di browser ini — tanpa rebuild. */
export function setApiUrl(url: string): void {
  if (typeof window === "undefined") return;
  const clean = url.trim().replace(/\/$/, "");
  if (clean) window.localStorage.setItem(LS_KEY, clean);
  else window.localStorage.removeItem(LS_KEY);
}

export function getDefaultApiUrl(): string {
  return DEFAULT_API;
}

export async function getHealth(): Promise<{ status: string; guide: string }> {
  const res = await fetch(`${getApiUrl()}/health`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/** Kirim pertanyaan, terima jawaban token-demi-token via callback. */
export async function streamChat(
  message: string,
  cb: StreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${getApiUrl()}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE: event dipisah oleh baris kosong (\n\n)
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const evt of events) {
      const line = evt.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (!payload) continue;
      let data: { type: string; content?: string; items?: Source[] };
      try {
        data = JSON.parse(payload);
      } catch {
        continue;
      }
      if (data.type === "token" && data.content) cb.onToken(data.content);
      else if (data.type === "sources" && data.items) cb.onSources(data.items);
      else if (data.type === "done") cb.onDone();
    }
  }
}
