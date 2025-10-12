/// <reference types="cypress" />

// Hits your real backend; adjust dates/range to ensure some data exists.

describe('Anomaly overlay (live backend)', () => {
  beforeEach(() => {
    cy.visit('/');
  });

  it('runs, toggles overlays, and resets cleanly', () => {
    // pick a safe range
    cy.get('[data-testid="filter-start"]').clear().type('2025-09-01');
    cy.get('[data-testid="filter-end"]').clear().type('2025-10-20');

    // make it easier to see anomalies if any
    cy.get('[data-testid="anoms-window"]').clear().type('{selectall}3');
    cy.get('[data-testid="anoms-z"]').clear().type('{selectall}2');

    // Run
    cy.get('[data-testid="btn-run"]').click();

    // Turn on anomalies; hook may have 0+ depending on real data
    cy.get('[data-testid="toggle-anoms"]').check();

    // If your backend returns none for this range, length can be 0; but the hook should exist
    cy.get('[data-testid="anomaly-list"]', { timeout: 10000 }).should('exist');

    // Toggle forecast on/off
    cy.get('[data-testid="toggle-forecast"]').check();
    cy.get('[data-testid="forecast-list"]').should('exist');

    // Reset restores defaults and re-runs
    cy.get('[data-testid="btn-reset"]').click();
    cy.get('[data-testid="toggle-anoms"]').should('not.be.checked');
    cy.get('[data-testid="toggle-forecast"]').should('not.be.checked');
  });
});
