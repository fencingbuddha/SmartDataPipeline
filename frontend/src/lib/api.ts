// frontend/src/lib/api.ts
const envBase = (import.meta.env.VITE_API_BASE || "").trim();
const isBrowser = typeof window !== "undefined";
const isCypress = isBrowser && Boolean((window as any)?.Cypress);
const DEFAULT_ORIGIN = isBrowser ? window.location.origin : "http://127.0.0.1:5173";
const API_BASE = isCypress ? "" : envBase;

if (isBrowser) {
  (window as any).__APP_ENV__ = {
    VITE_TEST_API_BASE: import.meta.env.VITE_TEST_API_BASE || "",
    VITE_TEST_AUTH_EMAIL: import.meta.env.VITE_TEST_AUTH_EMAIL || "",
    VITE_TEST_AUTH_PASSWORD: import.meta.env.VITE_TEST_AUTH_PASSWORD || "",
    VITE_AUTH_STORAGE_PREFIX: import.meta.env.VITE_AUTH_STORAGE_PREFIX || "sdp_",
  };
}

function resolveUrl(path: string): string {
  if (path.startsWith("http")) return path;
  if (API_BASE) {
    if (API_BASE.endsWith("/") && path.startsWith("/")) {
      return `${API_BASE.slice(0, -1)}${path}`;
    }
    return `${API_BASE}${path}`;
  }
  return new URL(path, DEFAULT_ORIGIN).href;
}
const PREFIX = (import.meta.env.VITE_AUTH_STORAGE_PREFIX || "sdp_").trim();

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type?: string;
};

export const tokenStore = {
  get access() {
    return localStorage.getItem(`${PREFIX}access`) || "";
  },
  get refresh() {
    return localStorage.getItem(`${PREFIX}refresh`) || "";
  },
  set(tokens: TokenPair) {
    localStorage.setItem(`${PREFIX}access`, tokens.access_token);
    localStorage.setItem(`${PREFIX}refresh`, tokens.refresh_token);
  },
  clear() {
    localStorage.removeItem(`${PREFIX}access`);
    localStorage.removeItem(`${PREFIX}refresh`);
  },
};

export function buildUrl(
  path: string,
  params?: Record<string, string | number | undefined>
) {
  const url = new URL(resolveUrl(path));
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "")
        url.searchParams.set(k, String(v));
    });
  }
  return url.toString();
}

let refreshing: Promise<string> | null = null;

async function doRefresh(): Promise<string> {
  if (!tokenStore.refresh) throw new Error("No refresh token");
  const res = await fetch(`${API_BASE}/api/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: tokenStore.refresh }),
  });
  if (!res.ok) throw new Error("Refresh failed");
  const data = (await res.json()) as TokenPair;
  tokenStore.set(data);
  return data.access_token;
}

export async function request<T>(
  path: string,
  init?: RequestInit & { retry?: boolean }
): Promise<T> {
  const url = resolveUrl(path);
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (tokenStore.access) headers.Authorization = `Bearer ${tokenStore.access}`;
  const res = await fetch(url, { ...init, headers });

  if ((res.status === 401 || res.status === 403) && !init?.retry) {
    // single-flight refresh
    if (!refreshing) refreshing = doRefresh().finally(() => (refreshing = null));
    const newAccess = await refreshing; // throws if refresh fails
    const retryHeaders: Record<string, string> = {
      ...(init?.headers as Record<string, string> | undefined),
      Authorization: `Bearer ${newAccess}`,
    };
    const retry = await fetch(url, { ...init, headers: retryHeaders, retry: true } as any);
    if (!retry.ok) {
      const text = await retry.text().catch(() => "");
      throw new Error(`${init?.method || "GET"} ${path} failed: ${retry.status} ${retry.statusText}${text ? ` - ${text}` : ""}`);
    }
    return retry.json() as Promise<T>;
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${init?.method || "GET"} ${path} failed: ${res.status} ${res.statusText}${text ? ` - ${text}` : ""}`);
  }
  return res.json() as Promise<T>;
}

export async function getJson<T>(
  path: string,
  params?: Record<string, any>,
  signal?: AbortSignal
): Promise<T> {
  return request<T>(buildUrl(path, params), { method: "GET", signal });
}

export async function postJson<T>(
  path: string,
  body?: any,
  signal?: AbortSignal
): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });
}

export const authApi = {
  async login(email: string, password: string) {
    const data = await postJson<TokenPair>("/api/auth/login", { email, password });
    tokenStore.set(data);
    return data;
  },
  async signup(email: string, password: string) {
    const data = await postJson<TokenPair>("/api/auth/signup", { email, password });
    tokenStore.set(data);
    return data;
  },
  logout() {
    tokenStore.clear();
  },
  get isAuthed() {
    return !!tokenStore.access;
  },
};
