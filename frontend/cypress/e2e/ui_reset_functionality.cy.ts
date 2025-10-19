/// <reference types="cypress" />
import type { Interception } from 'cypress/types/net-stubbing';

/**
 * UAT: Reset restores defaults and triggers a fresh fetch
 * Verifies:
 *  - Network call after Reset includes default query params
 *  - Overlays are OFF
 *  - UI is still usable (Run/Reset buttons, chart SVG, table present)
 */

describe('Dashboard reset behavior', () => {
  beforeEach(() => {
    // Deterministic daily response so render is instant & stable.
    cy.intercept('GET', '**/api/metrics/daily*', {
      statusCode: 200,
      body: [
        { metric_date: '2025-09-18', source: 'demo-source', metric: 'events_total', value_sum: 7 },
        { metric_date: '2025-09-19', source: 'demo-source', metric: 'events_total', value_sum: 11 },
        { metric_date: '2025-09-20', source: 'demo-source', metric: 'events_total', value_sum: 27 },
      ],
    }).as('getDaily');

    // App may call anomaly or forecast after reset; support both.
    cy.intercept('GET', '**/api/metrics/anomaly/**', { statusCode: 200, body: { points: [] } }).as('getAnoms');
    cy.intercept('GET', '**/api/forecast/daily*', { statusCode: 200, body: [] }).as('getForecast');

    cy.visit('/');

    // Ensure app booted and fetched.
    cy.wait('@getDaily');

    // Assert obvious, stable controls instead of wrapper testids.
    cy.contains('button', /^Run$/).should('exist');
    cy.contains('button', /^Reset$/).should('exist');
    cy.get('svg', { timeout: 10000 }).should('exist');     // chart (Recharts)
    cy.get('table', { timeout: 10000 }).should('exist');   // data table
  });

  it('[UAT-FR6C-005] Reset returns to defaults and re-fetches', () => {
    // 1) Dirty state (turn overlays ON).
    cy.get('[data-testid="toggle-anoms"]').click({ force: true });
    cy.get('[data-testid="toggle-forecast"]').click({ force: true });

    // 2) Click Reset.
    cy.get('[data-testid="btn-reset"]').click();

    // 3) Daily re-fetch should use DEFAULT params.
    cy.wait('@getDaily').then(({ request }) => {
      const url = new URL(request.url);
      const qs = Object.fromEntries(url.searchParams.entries());

      expect(qs.source_name).to.eq('demo-source');
      expect(qs.metric).to.eq('events_total');
      if ('range' in qs) expect(qs.range).to.eq('7');
      if ('date_range' in qs) expect(qs.date_range).to.eq('7');
      if ('window_n' in qs) expect(qs.window_n).to.eq('7');
      if ('z_thresh' in qs) expect(qs.z_thresh).to.eq('3');
    });

    // 4) Overlays OFF in the UI.
    cy.get('[data-testid="toggle-anoms"]').should('not.be.checked');
    cy.get('[data-testid="toggle-forecast"]').should('not.be.checked');

    // 5) If a follow-up request happens after reset (anomaly OR forecast), validate defaults.
    cy.wait(300);
    cy.get<Interception[]>('@getAnoms.all').then((anomsCalls) => {
      const alias = Array.isArray(anomsCalls) && anomsCalls.length > 0 ? '@getAnoms.all' : '@getForecast.all';
      cy.get<Interception[]>(alias).then((calls) => {
        if (Array.isArray(calls) && calls.length > 0) {
          const last = calls[calls.length - 1];
          const url = new URL(last.request.url);
          const qs = Object.fromEntries(url.searchParams.entries());
          if ('source_name' in qs) expect(qs.source_name).to.eq('demo-source');
          if ('metric' in qs) expect(qs.metric).to.eq('events_total');
        }
      });
    });

    // 6) Sanity: dashboard still renders after reset.
    cy.contains('button', /^Run$/).should('exist');
    cy.get('svg').should('exist');
    cy.get('table').should('exist');
  });
});
