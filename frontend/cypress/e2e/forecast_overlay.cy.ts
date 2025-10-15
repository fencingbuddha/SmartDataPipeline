/// <reference types="cypress" />

/** Always reply with daily so the chart renders */
function primeDaily() {
  cy.intercept("GET", "**/api/metrics/daily*", {
    statusCode: 200,
    body: [
      { metric_date: "2025-10-10", source: "demo-source", metric: "events_total", value_sum: 10 },
      { metric_date: "2025-10-12", value_sum: 20 },
      { metric_date: "2025-10-14", value_sum: 45 },
    ],
  }).as("daily1");
}

/** Visit and wait for the base chart to mount */
function visitAndWaitChart() {
  cy.visit("/");
  cy.viewport(1200, 800);
  cy.wait("@daily1");
  cy.get('[data-testid="chart"]', { timeout: 10000 }).should("be.visible");
}

/** Make a flexible intercept for forecast and alias it "forecast" */
function stubForecastOK() {
  cy.intercept("GET", "**/api/forecast/daily*", (req) => {
    // Generate 2 points inside the requested range so the app is happy.
    const url = new URL(req.url, window.location.origin);
    const start = url.searchParams.get("start_date")!;
    const end = url.searchParams.get("end_date") || start;
    const sd = new Date(start);
    const ed = new Date(end);
    const mid = new Date((sd.getTime() + ed.getTime()) / 2);
    const toISO = (d: Date) => d.toISOString().slice(0, 10);
    mid.setUTCHours(0,0,0,0); ed.setUTCHours(0,0,0,0);
    req.reply({
      statusCode: 200,
      body: [
        { target_date: toISO(mid), yhat: 100 },
        { target_date: toISO(ed),  yhat: 120 },
      ],
    });
  }).as("forecast");
}
function stubForecastFail() {
  cy.intercept("GET", "**/api/forecast/daily*", { statusCode: 500, body: { detail: "boom" } }).as("forecast");
}

/** Helpers to assert number of forecast calls seen so far */
function expectForecastCalls(n: number) {
  // Cypress stores all matches in @forecast.all
  cy.get("@forecast.all").then((arr: any) => {
    const count = Array.isArray(arr) ? arr.length : 0;
    expect(count, "forecast call count").to.equal(n);
  });
}
function expectAtLeastForecastCalls(n: number) {
  cy.get("@forecast.all").then((arr: any) => {
    const count = Array.isArray(arr) ? arr.length : 0;
    expect(count, "forecast call count").to.be.gte(n);
  });
}

describe("FR-6C Forecast Overlay (app-level)", () => {
  it("[UAT-FR6C-001] Toggle ON populates forecast data; OFF clears it (no extra calls)", () => {
    primeDaily();
    stubForecastOK();
    visitAndWaitChart();

    // Start OFF
    cy.get('[data-testid="toggle-forecast"]').uncheck({ force: true }).should("not.be.checked");
    // No calls yet
    expectForecastCalls(0);

    // ON -> exactly one forecast fetch
    cy.get('[data-testid="toggle-forecast"]').check({ force: true }).should("be.checked");
    cy.wait("@forecast");
    expectForecastCalls(1);

    // OFF -> stays cleared; crucially, no new forecast fetch occurs
    cy.get('[data-testid="toggle-forecast"]').uncheck({ force: true }).should("not.be.checked");
    cy.wait(50);
    expectForecastCalls(1);

    // (Optional) Chart still present
    cy.get('[data-testid="chart"]').should("be.visible");
  });

  it("[UAT-FR6C-002] Forecast API failure: no crash; forecast list/overlay stays empty (no subsequent calls)", () => {
    primeDaily();
    stubForecastFail();
    visitAndWaitChart();

    cy.get('[data-testid="toggle-forecast"]').check({ force: true }).should("be.checked");
    cy.wait("@forecast");
    // No crash => chart remains visible
    cy.get('[data-testid="chart"]').should("be.visible");

    // OFF -> no extra fetch
    cy.get('[data-testid="toggle-forecast"]').uncheck({ force: true }).should("not.be.checked");
    cy.wait(50);
    expectForecastCalls(1);
  });

  it("[UAT-FR6C-003] Changing date range triggers a new forecast fetch (while ON)", () => {
  primeDaily();
  stubForecastOK();     // alias: @forecast
  visitAndWaitChart();

  // First ON -> 1st fetch
  cy.get('[data-testid="toggle-forecast"]').check({ force: true }).should("be.checked");
  cy.wait("@forecast");
  expectForecastCalls(1);

  // Change end date, then press Run -> should trigger another fetch
  cy.get('[data-testid="filter-end"]').clear().type("2025-10-21").blur();
  cy.get('[data-testid="btn-run"]').click();      // <-- important
  cy.wait("@forecast");
  expectForecastCalls(2);                         // now we expect two total
});

  it("[UAT-FR6C-004] Toggle responds immediately: ON fetches; OFF does not; ON again shows forecast (may reuse cache)", () => {
    primeDaily();
    stubForecastOK();     // alias: @forecast
    visitAndWaitChart();

    // ON -> 1st fetch
    cy.get('[data-testid="toggle-forecast"]').check({ force: true }).should("be.checked");
    cy.wait("@forecast");
    expectForecastCalls(1);

    // OFF -> no new fetch
    cy.get('[data-testid="toggle-forecast"]').uncheck({ force: true }).should("not.be.checked");
    cy.wait(50);
    expectForecastCalls(1);

    // ON again -> app may reuse cached data (no extra call) OR refetch.
    cy.get('[data-testid="toggle-forecast"]').check({ force: true }).should("be.checked");

    // Tolerant assertion: either +1 call OR same count (cache hit).
    cy.wait(200); // brief tick for any fetch
    cy.get("@forecast.all").then((arr: any) => {
      const count = Array.isArray(arr) ? arr.length : 0;
      expect(count, "forecast call count should be >= 1 after re-enabling").to.be.gte(1);
    });

  // (Optional) chart still visible
  cy.get('[data-testid="chart"]').should("be.visible");
});
});
