/// <reference types="cypress" />

// Assumes cypress.config has baseUrl set to your dev server (e.g., http://localhost:5173)

describe('Anomaly overlay (stubbed)', () => {
  it('shows flagged anomalies and passes window/z to the API', () => {
    // Stub base series
    cy.intercept('GET', '**/api/metrics/daily*', {
      statusCode: 200,
      body: [
        { metric_date: '2025-09-01', source: 'demo-source', metric: 'events_total', value_sum: 10 },
        { metric_date: '2025-09-02', value_sum: 12 },
        { metric_date: '2025-09-03', value_sum: 9  },
        { metric_date: '2025-09-18', value_sum: 7  },
        { metric_date: '2025-09-19', value_sum: 11 },
        { metric_date: '2025-09-20', value_sum: 27 },
      ],
    }).as('getDaily');

    // Capture anomalies request and assert params
    cy.intercept('GET', '**/api/metrics/anomaly/rolling*', (req) => {
      const u = new URL(req.url);
      expect(u.searchParams.get('window')).to.exist;
      expect(u.searchParams.get('z_thresh')).to.exist;
      req.reply({
        statusCode: 200,
        body: [
          { date: '2025-09-20', value: 27, z: 3.8, is_anomaly: true },
        ],
      });
    }).as('getAnoms');

    cy.visit('/');

    // Set dates (use your real min/max if needed)
    cy.get('[data-testid="filter-start"]').clear().type('2025-09-01');
    cy.get('[data-testid="filter-end"]').clear().type('2025-10-20');

    // Tune window/z before enabling overlay
    cy.get('[data-testid="anoms-window"]').clear().type('3');
    cy.get('[data-testid="anoms-z"]').clear().type('2');

    // Run base fetch
    cy.get('[data-testid="btn-run"]').click();
    cy.wait('@getDaily');

    // Toggle anomalies -> triggers overlay fetch with our params
    cy.get('[data-testid="toggle-anoms"]').check();
    cy.wait('@getAnoms');

    // Assert invisible hook reflects anomaly
    cy.get('[data-testid="anomaly-list"] li')
      .should('have.length.at.least', 1)
      .first()
      .should('have.attr', 'data-date', '2025-09-20');
  });
});
