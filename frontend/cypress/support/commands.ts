/// <reference types="cypress" />

// Safe Cypress helpers: no hard-coded secrets, fail fast if missing,
// and a login flow that works against the FastAPI backend in local/CI.

type VisitOptions = Cypress.VisitOptions;

/** Read env from Cypress or window.__APP_ENV__ (fallback only for non-secrets). */
const readEnv = (key: string): string | undefined => {
  const fromCypress = Cypress.env(key);
  if (typeof fromCypress === "string" && fromCypress.trim()) return String(fromCypress);
  // Allow frontend to expose test-only vars when running via Vite preview
  const fromWindow = typeof window !== "undefined" ? (window as any).__APP_ENV__?.[key] : undefined;
  if (typeof fromWindow === "string" && fromWindow.trim()) return String(fromWindow);
  return undefined;
};

/** Non-secret defaults are OK. */
export const API_BASE_URL = readEnv("VITE_TEST_API_BASE") || "http://127.0.0.1:8000";
export const AUTH_PREFIX = readEnv("VITE_AUTH_STORAGE_PREFIX") || "sdp_";

/** Secrets: NO defaults. Force explicit config via .env.cypress.local or CI. */
export const AUTH_EMAIL = readEnv("VITE_TEST_AUTH_EMAIL");
export const AUTH_PASSWORD = readEnv("VITE_TEST_AUTH_PASSWORD");

if (!AUTH_EMAIL || !AUTH_PASSWORD) {
  throw new Error(
    "Missing test creds: set VITE_TEST_AUTH_EMAIL and VITE_TEST_AUTH_PASSWORD in .env.cypress.local or CI secrets."
  );
}

/** Perform a login; if the user doesn't exist, create then login. */
const ensureToken = (): Cypress.Chainable<{ access_token: string; refresh_token?: string }> => {
  const loginReq = () =>
    cy
      .request({
        method: "POST",
        url: `${API_BASE_URL}/api/auth/login`,
        headers: { "Content-Type": "application/json" },
        body: { email: AUTH_EMAIL, password: AUTH_PASSWORD },
        failOnStatusCode: false,
        log: false, // don't echo creds
      })
      .then((res) => {
        if (res.status === 200 && res.body?.access_token) return res.body;
        // If login failed (e.g., 401/404), try to sign up then login again
        return cy
          .request({
            method: "POST",
            url: `${API_BASE_URL}/api/auth/signup`,
            headers: { "Content-Type": "application/json" },
            body: { email: AUTH_EMAIL, password: AUTH_PASSWORD },
            failOnStatusCode: false,
            log: false,
          })
          .then(() =>
            cy
              .request({
                method: "POST",
                url: `${API_BASE_URL}/api/auth/login`,
                headers: { "Content-Type": "application/json" },
                body: { email: AUTH_EMAIL, password: AUTH_PASSWORD },
                log: false,
              })
              .then((r2) => r2.body),
          );
      });

  return loginReq().then((body) => {
    const token = body?.access_token as string | undefined;
    if (!token) throw new Error("Login did not return access_token");
    return body;
  });
};

/** Public helper: fetch only the access token (string). */
export const fetchToken = (): Cypress.Chainable<string> =>
  ensureToken().then((b) => b.access_token as string);

/** Convenience builder for Authorization header. */
export const authHeader = (token: string) => ({ Authorization: `Bearer ${token}` });

/** Append an auth-bypass flag to app URLs so the app doesn't auto-redirect. */
const appendAuthParam = (target: string): string => {
  const base = Cypress.config("baseUrl") || "http://localhost:5173";
  const url = new URL(target, target.startsWith("http") ? undefined : base);
  if (!url.searchParams.has("auth")) url.searchParams.append("auth", "off");
  return url.toString();
};

/** Normalize visit args to (url, options). */
const normalizeVisitArgs = (
  url: string | Partial<VisitOptions>,
  options?: Partial<VisitOptions>,
) => {
  if (typeof url === "string") return { url, options: options ?? {} };
  const opts = { ...(url || {}) } as Partial<VisitOptions> & { url?: string };
  const targetUrl = typeof opts.url === "string" ? opts.url : "/";
  delete (opts as any).url;
  return { url: targetUrl, options: opts };
};

// --- Custom command: cy.login() returns the JWT access_token ---
declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Cypress {
    interface Chainable {
      /** Returns the JWT access token obtained from the API. */
      login(): Chainable<string>;
    }
  }
}

Cypress.Commands.add("login", () => fetchToken());

// --- Overwrite cy.visit to inject tokens into localStorage before app loads ---
Cypress.Commands.overwrite(
  "visit",
  (
    originalFn,
    url: string | Partial<VisitOptions>,
    options?: Partial<VisitOptions>,
  ) => {
    const { url: targetUrl, options: visitOpts } = normalizeVisitArgs(url, options);
    const finalUrl = appendAuthParam(targetUrl);

    return ensureToken().then((tokens) => {
      const existingOnBeforeLoad = visitOpts?.onBeforeLoad;
      const mergedOpts: Partial<VisitOptions> = {
        ...visitOpts,
        onBeforeLoad(win: Window, ...rest: any[]) {
          try {
            win.localStorage.setItem(`${AUTH_PREFIX}access`, tokens.access_token);
            if (tokens.refresh_token) {
              win.localStorage.setItem(`${AUTH_PREFIX}refresh`, tokens.refresh_token);
            }
          } finally {
            existingOnBeforeLoad?.(win, ...rest);
          }
        },
      };

      return originalFn(finalUrl, mergedOpts);
    });
  },
);

export {};