/// <reference types="cypress" />

describe("Reliability drawer", () => {
  const mock = {
    score: 88.7,
    grade: "A",
    summary: { mae: 2.1234, rmse: 3.4, mape: 4.5, smape: 4.2 },
  };

  beforeEach(() => {
    cy.intercept("GET", "/api/forecast/reliability*", {
      statusCode: 200,
      body: mock,
    }).as("getReliability");
  });

  it("opens the details drawer when the badge is clicked", () => {
    cy.visit("/");
    cy.wait("@getReliability");
    cy.findByTestId("rel-badge").click();
    cy.findByTestId("rel-drawer").should("exist");
  });

  it("closes the drawer when the Close button is pressed", () => {
    cy.visit("/");
    cy.wait("@getReliability");
    cy.findByTestId("rel-badge").click();
    cy.findByRole("button", { name: /close/i }).click();
    cy.findByTestId("rel-drawer").should("not.exist");
  });

  it("shows header text and summary values", () => {
    cy.visit("/");
    cy.wait("@getReliability");
    cy.findByTestId("rel-badge").click();

    cy.findByTestId("rel-drawer")
      .should("be.visible")
      .within(() => {
        cy.contains(/Composite score 89 · Grade A/).should("exist");
        cy.contains("td", "MAE").siblings().last().should("contain.text", "2.123");
        cy.contains("td", "RMSE").siblings().last().should("contain.text", "3.4");
        cy.contains("td", "MAPE").siblings().last().should("contain.text", "4.50%");
        cy.contains("td", "sMAPE").siblings().last().should("contain.text", "4.20%");
      });
  });

  it("closes on backdrop click and on Escape", () => {
    cy.visit("/");
    cy.wait("@getReliability");
    cy.findByTestId("rel-badge").click();

    cy.findByTestId("rel-drawer").should("exist");

    cy.findByTestId("rel-backdrop").click("topLeft", { force: true });
    cy.findByTestId("rel-drawer").should("not.exist");

    // Re-open and test Escape
    cy.findByTestId("rel-badge").click();
    cy.get("body").type("{esc}");
    cy.findByTestId("rel-drawer").should("not.exist");
  });
});
