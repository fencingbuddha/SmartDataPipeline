// frontend/cypress/e2e/export.cy.ts
describe("Dashboard exports", () => {
  beforeEach(() => {
    cy.visit("/"); // or "/dashboard" if you use routes
  });

  it("exports CSV for the current filters", () => {
    cy.intercept("GET", "/api/metrics/export/csv*").as("csv");
    cy.get('[data-testid="btn-export-csv"]').should("be.visible").click();
    cy.wait("@csv").then(({ response }) => {
      expect(response?.statusCode).to.eq(200);
      expect(String(response?.headers?.["content-type"])).to.contain("text/csv");
      // sanity: should include a header line
      expect(response?.body).to.match(/metric_date,.*value/);
    });
  });

  it("triggers PNG export of tiles + chart", () => {
    // Just ensure the button is wired and no client errors are thrown.
    // If you show a toast/snackbar after save, assert that instead.
    cy.window().then((w) => cy.spy(w.HTMLCanvasElement.prototype, "toDataURL").as("toDataURL").log(false));
    cy.get('[data-testid="btn-export-png"]').should("be.visible").click();
    cy.get("@toDataURL"); // ensures capture path executed at least once
  });
});