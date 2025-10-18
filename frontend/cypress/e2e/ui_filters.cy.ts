describe("FR-7 UI Filters + E2E", () => {
  beforeEach(() => {
    cy.intercept("GET", "**/api/metrics/daily*", (req) => {
      // Assert query params exist
      expect(req.query).to.have.property("source_name");
      expect(req.query).to.have.property("metric");
      req.reply({statusCode: 200, body: [
        { metric_date: "2025-09-18", source: "demo-source", metric: "events_total", value: 7 },
        { metric_date: "2025-09-19", value: 11 },
      ]});
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
    cy.get('[data-testid="chart"]').should("be.visible");
  });

  it("[UAT-FR7-002] Reset restores defaults and re-fetches", () => {
    cy.get('[data-testid="btn-reset"]').click();
    cy.wait("@daily");
    cy.get('[data-testid="chart"]').should("be.visible");
  });

  it("[UAT-FR7-003] Empty-state shown when API returns []", () => {
    cy.intercept("GET", "**/api/metrics/daily*", { statusCode: 200, body: [] }).as("empty");
    cy.get('[data-testid="btn-run"]').click();
    cy.wait("@empty");
    cy.get('[data-testid="empty-state"]').should("be.visible");
  });
});
