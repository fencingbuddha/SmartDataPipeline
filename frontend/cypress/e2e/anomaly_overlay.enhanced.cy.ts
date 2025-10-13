/// <reference types="cypress" />

/**
 * [UAT-FR4-004] Live anomaly flow + toggle interactions
 * Steps: Run, enable anomalies, adjust z/window, disable
 * Expected: Overlay responds to toggle and param changes; queries include z_thresh & window
 */
describe('FR-4 Anomaly overlay — enhanced (live-style)', () => {
  beforeEach(() => {
    cy.intercept('GET', '**/api/metrics/anomaly/rolling*', (req) => {
      const u = new URL(req.url);
      expect(u.searchParams.get('window')).to.exist;
      expect(u.searchParams.get('z_thresh')).to.exist;
      req.reply({ statusCode: 200, body: [{ date: '2025-09-20', value: 27, z: 3.8, is_anomaly: true }] });
    }).as('getAnoms');
    cy.intercept('GET', '**/api/metrics/daily*').as('getDaily');

    cy.visit('/');
    cy.get('[data-testid="filter-start"]').clear().type('2025-09-01');
    cy.get('[data-testid="filter-end"]').clear().type('2025-10-12');
    cy.get('[data-testid="btn-run"]').click();
    cy.wait('@getDaily');
  });

  it('[UAT-FR4-004] Enable → adjust → disable anomalies reflects on chart', () => {
    cy.get('[data-testid="toggle-anoms"]').check();
    cy.wait('@getAnoms');
    cy.get('[data-testid="anomaly-list"]');
    cy.get('[data-testid="anomaly-list"] li')
      .should('have.length.at.least', 1)
      .first()
      .should('have.attr', 'data-date', '2025-09-20');

    cy.get('[data-testid="anoms-z"]').clear().type('{selectall}2{enter}');
    cy.wait('@getAnoms');
    cy.get('[data-testid="anoms-window"]').clear().type('{selectall}5{enter}');
    cy.wait('@getAnoms');

    cy.get('[data-testid="toggle-anoms"]').uncheck();
    cy.get('[data-testid="anomaly-list"]');
    cy.get('[data-testid="anomaly-list"]').should('not.be.visible');
  });
});
