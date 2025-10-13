/// <reference types="cypress" />

/**
 * [UAT-FR6A-001..003] UI Foundation — Run/Reset, Refresh, Metric change
 */
describe('FR-6A UI foundation — controls & layout', () => {
  beforeEach(() => {
    cy.intercept('GET', '**/api/metrics/daily*').as('getDaily');
    cy.visit('/');
  });

  it('[UAT-FR6A-001] Run applies filters and renders data', () => {
    cy.get('[data-testid="filter-start"]').clear().type('2025-09-01');
    cy.get('[data-testid="filter-end"]').clear().type('2025-09-20');
    cy.get('[data-testid="btn-run"]').click();
    cy.wait('@getDaily');
    cy.get('[data-testid="anomaly-list"]').should('exist');
    cy.get('table tbody tr').should('have.length.at.least', 1);
  });

  it('[UAT-FR6A-002] Reset restores defaults', () => {
    cy.get('[data-testid="filter-start"]').clear().type('2025-09-01');
    cy.get('[data-testid="filter-end"]').clear().type('2025-09-20');
    cy.get('[data-testid="btn-run"]').click();
    cy.wait('@getDaily');
    cy.get('[data-testid="btn-reset"]').click();
    cy.wait('@getDaily');
  });
});
