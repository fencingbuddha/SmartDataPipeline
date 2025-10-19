/// <reference types="cypress" />

describe("FR-7 UI Filters + E2E", () => {
  beforeEach(() => {
    // Default intercept: return a small, deterministic series
    cy.intercept("GET", "**/api/metrics/daily*", (req) => {
      // Assert query params exist
      expect(req.query).to.have.property("source_name");
      expect(req.query).to.have.property("metric");

      req.reply({
        statusCode: 200,
        body: [
          { metric_date: "2025-09-18", source: "demo-source", metric: "events_total", value_sum: 7 },
          { metric_date: "2025-09-19", source: "demo-source", metric: "events_total", value_sum: 11 },
        ],
      });
    }).as("daily");

    cy.visit("/");
    cy.viewport(1200, 800);
  });

  it("[UAT-FR7-001] Run applies filters and renders data", () => {
    cy.get('[data-testid="filter-source"]').select("demo-source");
    cy.get('[data-testid="filter-metric"]').select("events_total");
    cy.get('[data-testid="filter-start"]').clear().type("2025-09-01").blur();
    cy.get('[data-testid="filter-end"]').clear().type("2025-10-20").blur();

    cy.get('[data-testid="btn-run"]').click();
    cy.wait("@daily");

    // Chart is an SVG (Recharts)
    cy.get("svg", { timeout: 10000 }).should("exist");
    // Table exists
    cy.get("table").should("exist");
  });

  it("[UAT-FR7-002] Reset restores defaults and re-fetches", () => {
    cy.get('[data-testid="btn-reset"]').click();
    cy.wait("@daily");

    cy.get("svg").should("exist");
    cy.get("table").should("exist");
  });

  it("[UAT-FR7-003] Empty-state shown when API returns []", () => {
    // Override the default intercept for this test to return empty.
    cy.intercept("GET", "**/api/metrics/daily*", { statusCode: 200, body: [] }).as("empty");

    cy.get('[data-testid="btn-run"]').click();
    cy.wait("@empty");

    // Assert the empty message that the app renders
    cy.contains(/No data for this selection\. Try a wider range\./i, { timeout: 4000 })
      .should("be.visible");

    // And the table should show no rows (just headers)
    cy.get("table").within(() => {
      cy.get("tbody tr").should("have.length.lte", 1); // 0 or a single 'no data' row
    });
  });
});
