// cypress/e2e/env_guard.cy.ts
it('has required test env', () => {
  const keys = ['VITE_TEST_API_BASE','VITE_TEST_AUTH_EMAIL','VITE_TEST_AUTH_PASSWORD','VITE_AUTH_STORAGE_PREFIX'];
  keys.forEach(k => expect(Cypress.env(k), `${k} missing`).to.be.a('string').and.not.be.empty);
});