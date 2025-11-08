const API_BASE = Cypress.env("VITE_TEST_API_BASE") || "http://127.0.0.1:8000";
const AUTH_EMAIL = Cypress.env("VITE_TEST_AUTH_EMAIL") || "demo@example.com";
const AUTH_PASSWORD = Cypress.env("VITE_TEST_AUTH_PASSWORD") || "demo123";

const fetchToken = () => {
  return cy
    .request({
      method: "POST",
      url: `${API_BASE}/api/auth/login`,
      body: { email: AUTH_EMAIL, password: AUTH_PASSWORD },
      failOnStatusCode: false,
    })
    .then((resp) => {
      if (resp.status === 200 && resp.body?.access_token) {
        return resp.body.access_token as string;
      }
      return cy
        .request({
          method: "POST",
          url: `${API_BASE}/api/auth/signup`,
          body: { email: AUTH_EMAIL, password: AUTH_PASSWORD },
        })
        .then((signupResp) => signupResp.body.access_token as string);
    });
};

describe("Health + metrics endpoints", () => {
  it("latency sane and date filter works", () => {
    cy.request("/api/health/latency")
      .its("body.paths")
      .then((paths: Array<{ path: string; p50_ms: number; p95_ms: number }>) => {
        const metricPath = paths.find((p) => p.path === "/api/metrics/daily");
        expect(metricPath, "metrics path recorded").to.exist;
        expect(metricPath!.p50_ms).to.be.lessThan(250);
        expect(metricPath!.p95_ms).to.be.lessThan(1000);
      });

    fetchToken().then((token) => {
      cy.request({
        url: "/api/metrics/daily",
        qs: {
          source_name: "demo-source",
          metric: "events_total",
          start_date: "2025-10-01",
          end_date: "2025-10-07",
        },
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
        .its("body.meta.params.start_date")
        .should("eq", "2025-10-01");
    });
  });
});
