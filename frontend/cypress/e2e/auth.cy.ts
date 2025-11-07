describe("Auth controls", () => {
  beforeEach(() => {
    cy.visit("/");
  });

  it("sign out clears tokens and shows the login screen", () => {
    cy.get('[data-testid="btn-signout"]').should("exist");

    cy.window().then((win) => {
      expect(
        win.localStorage.getItem(`${Cypress.env("AUTH_STORAGE_PREFIX") || "sdp_"}access`),
      ).to.be.a("string");
    });

    cy.get('[data-testid="btn-signout"]').click();

    cy.contains("[data-testid='login-title']", "Sign in").should("be.visible");

    cy.window().then((win) => {
      expect(
        win.localStorage.getItem(`${Cypress.env("AUTH_STORAGE_PREFIX") || "sdp_"}access`),
      ).to.be.null;
    });
  });
});
