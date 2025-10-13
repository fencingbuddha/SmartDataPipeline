const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export function buildUrl(path: string, params?: Record<string, string | number | undefined>) {
  const url = new URL(path.startsWith("http") ? path : `${API_BASE}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
    });
  }
  return url.toString();
}

export async function getJson<T>(path: string, params?: Record<string, any>, signal?: AbortSignal): Promise<T> {
  const res = await fetch(buildUrl(path, params), { signal });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`GET ${path} failed: ${res.status} ${res.statusText} ${text ? `- ${text}` : ""}`);
  }
  return res.json() as Promise<T>;
}
