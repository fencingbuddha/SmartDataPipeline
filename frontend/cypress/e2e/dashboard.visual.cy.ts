/// <reference types="cypress" />

// Visual baseline with forecast + anomalies toggled.
describe("Metric Daily overlays visual (@visual)", () => {
  beforeEach(() => {
    // Stub daily KPI data so the chart is deterministic.
    cy.intercept("GET", "**/api/metrics/daily*", {
      statusCode: 200,
      body: [
        { metric_date: "2025-09-01", source: "demo-source", metric: "events_total", value_sum: 10 },
        { metric_date: "2025-09-02", value_sum: 12 },
        { metric_date: "2025-09-03", value_sum: 9 },
        { metric_date: "2025-09-18", value_sum: 7 },
        { metric_date: "2025-09-19", value_sum: 11 },
        { metric_date: "2025-09-20", value_sum: 27 },
      ],
    }).as("daily");

    // Stub forecast points inside the range.
    cy.intercept("GET", "**/api/forecast/daily*", {
      statusCode: 200,
      body: [
        { target_date: "2025-09-02", yhat: 11 },
        { target_date: "2025-09-03", yhat: 10 },
        { target_date: "2025-09-19", yhat: 12 },
        { target_date: "2025-09-20", yhat: 20 },
      ],
    }).as("forecast");

    // Stub anomalies with one obvious spike.
    cy.intercept("GET", "**/api/metrics/anomaly/**", {
      statusCode: 200,
      body: [{ metric_date: "2025-09-20", value_sum: 27, z: 3.8, is_anomaly: true }],
    }).as("anoms");
  });

  it("matches baseline with forecast + anomalies", () => {
    cy.viewport(1200, 800);

    // Lock DPR to reduce pixel-diff noise across environments
    cy.visit("/", {
      onBeforeLoad(win) {
        // @ts-ignore
        win.devicePixelRatio = 1;
      },
    });

    // Ensure a known range + selections
    cy.get('[data-testid="filter-start"]').clear().type("2025-09-01").blur();
    cy.get('[data-testid="filter-end"]').clear().type("2025-10-20").blur();
    cy.get('[data-testid="filter-source"]').select("demo-source");
    cy.get('[data-testid="filter-metric"]').select("events_total");

    // Run and wait for the base series
    cy.get('[data-testid="btn-run"]').click();
    cy.wait("@daily");

    // Enable both overlays and wait for their calls
    cy.get('[data-testid="toggle-forecast"]').check({ force: true });
    cy.get('[data-testid="toggle-anoms"], [data-testid="toggle-anomalies"]').first().check({ force: true });
    cy.wait(["@forecast", "@anoms"], { timeout: 10000 });

    // Ensure the chart is visible
    cy.get("svg", { timeout: 10000 }).should("be.visible");

    // --- OPTION B: disable animations/transitions just for this test ---
    cy.document().then((doc) => {
      const style = doc.createElement("style");
      style.setAttribute("data-cy", "disable-animations");
      style.innerHTML = `
        /* Kill animations/transitions that can change pixels between frames */
        .recharts-wrapper *, svg *, * {
          animation: none !important;
          transition: none !important;
        }
      `;
      doc.head.appendChild(style);
    });

    // Small settle so the DOM reflects the non-animated state
    cy.wait(250);

    // Viewport snapshot with NUMERIC threshold (plugin honors numbers)
    // Tweak 0.8–1.5 based on your environment/CI variance.
    cy.compareSnapshot("metric-daily-overlays", 1.2);
  });
});
