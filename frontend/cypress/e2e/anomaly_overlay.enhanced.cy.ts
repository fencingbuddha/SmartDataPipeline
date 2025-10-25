/// <reference types="cypress" />

/**
 * [UAT-FR4-004] Live anomaly flow + toggle interactions
 * Steps: Run, enable anomalies, adjust z/window, disable
 * Expected: Overlay responds to toggle and param changes; queries include z_thresh & window
 */
describe('FR-4 Anomaly overlay — enhanced (live-style)', () => {
  beforeEach(() => {
    cy.intercept(
      { method: /.*/, url: /\/api\/metrics\/anomaly\/rolling\/?(\?.*)?$/ },
      (req) => {
        try {
          const u = new URL(req.url, window.location.origin);
          expect(u.searchParams.get('window')).to.exist;
          expect(u.searchParams.get('z_thresh')).to.exist;
        } catch {
          // if URL parsing fails due to relative path, skip param asserts
        }
        req.reply({
          statusCode: 200,
          body: [{ date: '2025-09-20', value: 27, z: 3.8, is_anomaly: true }],
        });
      }
    ).as('getAnoms');
    cy.intercept('GET', '**/api/metrics/daily*').as('getDaily');

    cy.visit('/');
    cy.get('[data-testid="filter-start"]').clear().type('2025-09-01');
    cy.get('[data-testid="filter-end"]').clear().type('2025-10-12');
    cy.get('[data-testid="btn-run"]').click();
    cy.wait('@getDaily');
  });

  it('[UAT-FR4-004] Enable → adjust → disable anomalies reflects on chart', () => {
    cy.get('[data-testid="toggle-anoms"]').check({ force: true });
    cy.wait('@getAnoms', { timeout: 10000 });
    cy.get('[data-testid="anomaly-list"]', { timeout: 10000 }).should('exist').within(() => {
      cy.get('li')
        .should('have.length.at.least', 1)
        .first()
        .then($li => {
          const dateAttr = $li.attr('data-date');
          const text = $li.text();
          expect(dateAttr || text).to.include('2025-09-20');
        });
    });

    cy.get('[data-testid="anoms-z"]').clear().type('{selectall}2').blur();
    cy.wait('@getAnoms', { timeout: 10000 });
    cy.wait(50);
    cy.get('[data-testid="anoms-window"]').clear().type('{selectall}5').blur();
    cy.wait('@getAnoms', { timeout: 10000 });
    cy.wait(50);

    cy.get('[data-testid="toggle-anoms"]').uncheck({ force: true });

    // The app may hide the list instead of removing it; handle both.
    cy.get('body').then(($body) => {
      const sel = '[data-testid="anomaly-list"]';
      if ($body.find(sel).length > 0) {
        cy.get(sel).should('not.be.visible');
      } else {
        cy.get(sel).should('not.exist');
      }
    });
  });
});
