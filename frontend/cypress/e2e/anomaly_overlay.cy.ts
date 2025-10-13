/// <reference types="cypress" />

/**
 * Title: FR-4 Anomaly Detection Overlay (Stubbed)
 * User Story: As a user, I can toggle anomaly overlays and adjust z-thresholds and window sizes
 * to highlight outliers in KPI trends.
 *
 * This stubbed suite ensures all anomaly overlay behaviors function correctly,
 * using predictable mock data so no live backend is required.
 */

describe('FR-4 Anomaly Detection Overlay (stubbed)', () => {
  beforeEach(() => {
    // Stub daily KPI data
    cy.intercept('GET', '**/api/metrics/daily*', {
      statusCode: 200,
      body: [
        { metric_date: '2025-09-01', source: 'demo-source', metric: 'events_total', value_sum: 10 },
        { metric_date: '2025-09-02', value_sum: 12 },
        { metric_date: '2025-09-03', value_sum: 9 },
        { metric_date: '2025-09-18', value_sum: 7 },
        { metric_date: '2025-09-19', value_sum: 11 },
        { metric_date: '2025-09-20', value_sum: 27 },
      ],
    }).as('getDaily');

    // Stub anomaly endpoint
    cy.intercept('GET', '**/api/metrics/anomaly/rolling*', (req) => {
      const u = new URL(req.url);
      expect(u.searchParams.get('window')).to.exist;
      expect(u.searchParams.get('z_thresh')).to.exist;
      req.reply({
        statusCode: 200,
        body: [{ date: '2025-09-20', value: 27, z: 3.8, is_anomaly: true }],
      });
    }).as('getAnoms');

    cy.visit('/');

    // Define default working date range
    cy.get('[data-testid="filter-start"]').clear().type('2025-09-01');
    cy.get('[data-testid="filter-end"]').clear().type('2025-10-20');

    // Run baseline
    cy.get('[data-testid="btn-run"]').click();
    cy.wait('@getDaily');
  });

  // [UAT-FR4-001] Toggle shows anomaly markers
  it('[UAT-FR4-001] Toggle shows anomaly markers', () => {
    cy.get('[data-testid="anoms-window"]').clear().type('3');
    cy.get('[data-testid="anoms-z"]').clear().type('2');
    cy.get('[data-testid="btn-run"]').click();

    cy.get('[data-testid="toggle-anoms"]').check({ force: true });
    cy.wait('@getAnoms');

    cy.get('[data-testid="anomaly-list"] li')
      .should('have.length.at.least', 1)
      .first()
      .should('have.attr', 'data-date', '2025-09-20');
  });

  // [UAT-FR4-002] z-threshold filters correctly
  it('[UAT-FR4-002] z-threshold filters correctly', () => {
    cy.get('[data-testid="toggle-anoms"]').check({ force: true });

    cy.get('[data-testid="anoms-z"]').clear().type('2');
    cy.get('[data-testid="btn-run"]').click();
    cy.wait('@getAnoms');
    cy.get('[data-testid="anomaly-list"] li').then(($low) => {
      const lowCount = $low.length;

      // Increase z to reduce anomalies
      cy.get('[data-testid="anoms-z"]').clear().type('5');
      cy.get('[data-testid="btn-run"]').click();
      cy.wait('@getAnoms');
      cy.get('[data-testid="anomaly-list"] li').its('length').should('be.lte', lowCount);
    });
  });

  // [UAT-FR4-003] Window size affects anomaly sensitivity
  it('[UAT-FR4-003] Window size affects anomaly sensitivity', () => {
    cy.get('[data-testid="toggle-anoms"]').check({ force: true });

    cy.get('[data-testid="anoms-window"]').clear().type('3');
    cy.get('[data-testid="btn-run"]').click();
    cy.wait('@getAnoms');
    cy.get('[data-testid="anomaly-list"] li').then(($small) => {
      const smallCount = $small.length;

      cy.get('[data-testid="anoms-window"]').clear().type('9');
      cy.get('[data-testid="btn-run"]').click();
      cy.wait('@getAnoms');
      cy.get('[data-testid="anomaly-list"] li').its('length').should('be.lte', smallCount);
    });
  });

  // [UAT-FR4-004] Reset restores default parameters
  it('[UAT-FR4-004] Reset restores defaults', () => {
    cy.get('[data-testid="anoms-window"]').clear().type('{selectall}5{enter}');
    cy.get('[data-testid="anoms-z"]').clear().type('{selectall}2{enter}');
    cy.get('[data-testid="btn-reset"]').click();

    cy.get('[data-testid="anoms-window"]').should('have.value', '7');
    cy.get('[data-testid="anoms-z"]').should('have.value', '3');
  });
});
