/// <reference types="cypress" />

/**
 * [UAT-FR6C] Forecast Overlay — band & line rendering (stubbed)
 * Validates forecast toggle, error handling, and redraw behavior using mocked data.
 */

describe('FR-6C Forecast Overlay — band & line rendering (stubbed)', () => {
  beforeEach(() => {
    // Stub base KPI data
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

    cy.visit('/');

    cy.get('[data-testid="quick-range"]').select('30'); // “Last 30 days”
    cy.get('[data-testid="btn-run"]').click();
    cy.wait('@getDaily');
  });


  it('[UAT-FR6C-001] Toggle ON shows forecast overlay; OFF hides it', () => {
  cy.intercept('GET', '**/api/forecast/daily?*', {
    statusCode: 200,
    body: [
      { target_date: '2025-09-21', yhat: 12, yhat_lower: 9, yhat_upper: 15 },
      { target_date: '2025-09-22', yhat: 14, yhat_lower: 10, yhat_upper: 17 },
    ],
  }).as('getForecast');

  cy.get('[data-testid="toggle-forecast"]').check({ force: true });
  cy.wait('@getForecast');
  
  cy.wait(500); 

  cy.get('[data-testid="forecast-line"]', { timeout: 10000 }).should('exist').and('be.visible');
  cy.get('[data-testid="forecast-band"]', { timeout: 10000 }).should('exist').and('be.visible');

  cy.get('[data-testid="toggle-forecast"]').uncheck({ force: true });
  cy.wait(300);
  cy.get('[data-testid="forecast-line"]').should('not.exist');
});


  it('[UAT-FR6C-002] Forecast API failure displays error banner', () => {
    cy.intercept('GET', '*forecast/daily*', {
      statusCode: 500,
      body: { ok: false, error: 'Forecast failed' },
    }).as('getForecastFail');

    cy.get('[data-testid="toggle-forecast"]').check({ force: true });
    cy.wait('@getForecastFail');

    cy.get('[data-testid="error-banner"]').should('contain.text', 'forecast').and('be.visible');
    cy.get('[data-testid="forecast-line"]').should('not.exist');
  });

  it('[UAT-FR6C-003] Changing date range re-runs forecast query', () => {
    cy.intercept('GET', '*forecast/daily*start_date=2025-09-01*', {
      statusCode: 200,
      body: [{ target_date: '2025-09-10', yhat: 11, yhat_lower: 8, yhat_upper: 13 }],
    }).as('getForecastRange1');

    cy.intercept('GET', '*forecast/daily*start_date=2025-09-15*', {
      statusCode: 200,
      body: [{ target_date: '2025-09-18', yhat: 15, yhat_lower: 12, yhat_upper: 18 }],
    }).as('getForecastRange2');

    cy.get('[data-testid="toggle-forecast"]').check({ force: true });
    cy.wait('@getForecastRange1');

    cy.get('[data-testid="filter-start"]').clear().type('2025-09-15');
    cy.get('[data-testid="filter-end"]').clear().type('2025-10-20');
    cy.get('[data-testid="btn-run"]').click();
    cy.wait('@getForecastRange2');

    cy.get('[data-testid="forecast-line"]').should('be.visible');
  });

  it('[UAT-FR6C-004] Toggle ON/OFF reflects immediately on chart', () => {
    cy.intercept('GET', '*forecast/daily*', {
      statusCode: 200,
      body: [{ target_date: '2025-09-20', yhat: 12, yhat_lower: 10, yhat_upper: 14 }],
    }).as('getForecast');

    cy.get('[data-testid="toggle-forecast"]').check({ force: true });
    cy.wait('@getForecast');

    cy.get('[data-testid="forecast-line"]').should('be.visible');

    cy.get('[data-testid="toggle-forecast"]').uncheck({ force: true });
    cy.get('[data-testid="forecast-line"]').should('not.exist');
  });
});
