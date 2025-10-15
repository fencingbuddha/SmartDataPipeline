// cypress/e2e/dashboard.visual.cy.ts
// Visual baseline with forecast + anomalies toggled.

describe("Metric Daily overlays visual (@visual)", () => {
  beforeEach(() => {
    // Stub daily KPI data (matches your UI's expected shape)
    cy.intercept("GET", "**/api/metrics/daily*", {
      statusCode: 200,
      body: [
        { metric_date: "2025-09-01", source: "demo-source", metric: "events_total", value_sum: 10 },
        { metric_date: "2025-09-02", value_sum: 12 },
        { metric_date: "2025-09-03", value_sum: 9 },
        { metric_date: "2025-09-18", value_sum: 7 },
        { metric_date: "2025-09-19", value_sum: 11 },
        { metric_date: "2025-09-20", value_sum: 27 }
      ],
    }).as("daily");

    // Stub forecast (target_date + yhat is common in your code)
    cy.intercept("GET", "**/api/forecast/daily*", {
      statusCode: 200,
      body: [
        { target_date: "2025-09-02", yhat: 11 },
        { target_date: "2025-09-03", yhat: 10 },
        { target_date: "2025-09-19", yhat: 12 },
        { target_date: "2025-09-20", yhat: 20 }
      ],
    }).as("forecast");

    // Stub anomalies (metric_date + value_sum + z)
    cy.intercept("GET", "**/api/metrics/anomaly/**", {
      statusCode: 200,
      body: [{ metric_date: "2025-09-20", value_sum: 27, z: 3.8, is_anomaly: true }],
    }).as("anoms");
  });

  it("matches baseline with forecast + anomalies", () => {
    cy.viewport(1200, 800);
    cy.visit("/");

    // Selectors may already be pre-filled; this ensures a valid range
    cy.get('[data-testid="filter-start"]').clear().type("2025-09-01").blur();
    cy.get('[data-testid="filter-end"]').clear().type("2025-10-20").blur();

    // (Optional) ensure correct source/metric
    cy.get('[data-testid="filter-source"]').select("demo-source");
    cy.get('[data-testid="filter-metric"]').select("events_total");

    // Run and wait for daily data (chart uses this to render)
    cy.get('[data-testid="btn-run"]').click();
    cy.wait("@daily");

    // Turn on overlays (support both possible testids)
    cy.get('[data-testid="toggle-forecast"]').click();
    cy.get('[data-testid="toggle-anoms"], [data-testid="toggle-anomalies"]').first().click();

    // Wait for the chart to appear and settle
    cy.get('[data-testid="chart"]').should("be.visible");
    cy.wait(300);

    // Snapshot only the chart; 0.5% threshold
    cy.get('[data-testid="chart"]').compareSnapshot("metric-daily-overlays", 0.5);
  });
});
