/// <reference types="cypress" />
// ***********************************************
// This example commands.ts shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************
//
//
// -- This is a parent command --
// Cypress.Commands.add('login', (email, password) => { ... })
//
//
// -- This is a child command --
// Cypress.Commands.add('drag', { prevSubject: 'element'}, (subject, options) => { ... })
//
//
// -- This is a dual command --
// Cypress.Commands.add('dismiss', { prevSubject: 'optional'}, (subject, options) => { ... })
//
//
// -- This will overwrite an existing command --
// Cypress.Commands.overwrite('visit', (originalFn, url, options) => { ... })
//
// declare global {
//   namespace Cypress {
//     interface Chainable {
//       login(email: string, password: string): Chainable<void>
//       drag(subject: string, options?: Partial<TypeOptions>): Chainable<Element>
//       dismiss(subject: string, options?: Partial<TypeOptions>): Chainable<Element>
//       visit(originalFn: CommandOriginalFn, url: string, options: Partial<VisitOptions>): Chainable<Element>
//     }
//   }
// }
type VisitOptions = Cypress.VisitOptions;

const API_BASE_URL: string =
  (Cypress.env("API_BASE_URL") as string) || "http://127.0.0.1:8000";
const AUTH_EMAIL: string =
  (Cypress.env("AUTH_EMAIL") as string) || "demo@example.com";
const AUTH_PASSWORD: string =
  (Cypress.env("AUTH_PASSWORD") as string) || "demo123";
const AUTH_PREFIX: string =
  (Cypress.env("AUTH_STORAGE_PREFIX") as string) || "sdp_";

const appendAuthParam = (target: string): string => {
  const base = Cypress.config("baseUrl") || "http://localhost:5173";
  const url = new URL(target, target.startsWith("http") ? undefined : base);
  if (!url.searchParams.has("auth")) {
    url.searchParams.append("auth", "off");
  }
  return url.toString();
};

const fetchTokens = () => {
  return cy
    .request({
      method: "POST",
      url: `${API_BASE_URL}/api/auth/login`,
      body: { email: AUTH_EMAIL, password: AUTH_PASSWORD },
      failOnStatusCode: false,
    })
    .then((resp) => {
      if (resp.status === 200 && resp.body?.access_token) {
        return resp.body;
      }
      return cy
        .request({
          method: "POST",
          url: `${API_BASE_URL}/api/auth/signup`,
          body: { email: AUTH_EMAIL, password: AUTH_PASSWORD },
        })
        .its("body");
    });
};

const normalizeVisitArgs = (
  url: string | Partial<VisitOptions>,
  options?: Partial<VisitOptions>,
) => {
  if (typeof url === "string") {
    return { url, options: options ?? {} };
  }
  const opts = { ...(url || {}) };
  const targetUrl = typeof opts.url === "string" ? opts.url : "/";
  delete opts.url;
  return { url: targetUrl, options: opts };
};

Cypress.Commands.overwrite(
  "visit",
  (
    originalFn,
    url: string | Partial<VisitOptions>,
    options?: Partial<VisitOptions>,
  ) => {
    const { url: targetUrl, options: visitOpts } = normalizeVisitArgs(
      url,
      options,
    );
    const finalUrl = appendAuthParam(targetUrl);

    return fetchTokens().then((tokens) => {
      const existingOnBeforeLoad = visitOpts?.onBeforeLoad;
      const mergedOpts: Partial<VisitOptions> = {
        ...visitOpts,
        onBeforeLoad(win: Window, ...rest: any[]) {
          win.localStorage.setItem(
            `${AUTH_PREFIX}access`,
            tokens.access_token,
          );
          win.localStorage.setItem(
            `${AUTH_PREFIX}refresh`,
            tokens.refresh_token,
          );
          existingOnBeforeLoad?.(win, ...rest);
        },
      };

      return originalFn(finalUrl, mergedOpts);
    });
  },
);

export {};
