/// <reference types="cypress" />

describe('Dashboard anomaly overlay', () => {
  const visitDash = () => cy.visit('/');

  it('shows overlay markers only when the toggle is ON', () => {
    cy.intercept('GET', '**/api/metrics/daily*', {
      statusCode: 200,
      body: [
        { metric_date: '2025-09-30', value: 6 },
        { metric_date: '2025-10-01', value: 14 },
        { metric_date: '2025-10-02', value: 8 },
        { metric_date: '2025-10-03', value: 120 },
      ],
    }).as('daily');

    cy.intercept('GET', '**/api/metrics/anomaly/rolling*', (req) => {
      req.reply([
        { date: '2025-09-30', value: 6, is_outlier: false },
        { date: '2025-10-01', value: 14, is_outlier: false },
        { date: '2025-10-02', value: 8, is_outlier: false },
        { date: '2025-10-03', value: 120, is_outlier: true, z: 4.2 },
      ]);
    }).as('anoms');

    visitDash();
    cy.wait('@daily');

    cy.get('[data-testid="anomaly-point"]').should('not.exist');
    cy.get('[data-testid="toggle-anomalies"]').should('not.be.disabled');

    cy.get('[data-testid="toggle-anomalies"]').click();
    cy.wait('@anoms');
    cy.get('[data-testid="anomaly-point"]').should('have.length.at.least', 1);

    cy.get('[data-testid="toggle-anomalies"]').click();
    cy.get('[data-testid="anomaly-point"]').should('not.exist');
  });

  it('disables the toggle and shows an empty state when there is no data', () => {
    cy.intercept('GET', '**/api/metrics/daily*', {
      statusCode: 200,
      body: [],
    }).as('dailyEmpty');

    visitDash();
    cy.wait('@dailyEmpty');

    cy.contains(/No data for this selection/i).should('be.visible');
    cy.get('[data-testid="toggle-anomalies"]').should('be.disabled');
  });

  it('shows an error banner when the daily API fails', () => {
    cy.intercept('GET', '**/api/metrics/daily*', {
      statusCode: 500,
      body: { detail: 'server blew up' },
    }).as('dailyErr');

    visitDash();
    cy.wait('@dailyErr');

    cy.contains('⚠️').should('be.visible');
    cy.contains(/Load failed|Error|server blew up/i).should('exist');
  });

   it('sends selected anomaly parameters (window & z) when fetching', () => {
    // Stub series
    cy.intercept('GET', '**/api/metrics/daily*', {
      statusCode: 200,
      body: [
        { metric_date: '2025-09-30', value: 6 },
        { metric_date: '2025-10-01', value: 14 },
        { metric_date: '2025-10-02', value: 8 },
        { metric_date: '2025-10-03', value: 120 },
      ],
    }).as('daily2');

    // Intercept anomalies and assert exact params
    cy.intercept('GET', '**/api/metrics/anomaly/rolling*', (req) => {
      expect(req.query.window, 'window').to.eq('3');
      expect(req.query.z_thresh, 'z_thresh').to.eq('2');
      req.reply([{ date: '2025-10-03', value: 120, is_outlier: true, z: 4.2 }]);
    }).as('anomsParams');

    visitDash();
    cy.wait('@daily2');

    // Helper: set a React-controlled number input reliably
    const setNumByLabel = (labelRe: RegExp, value: string) => {
      cy.contains('label', labelRe)
        .parent()
        .find('input')
        .then(($el) => {
          const input = $el[0] as HTMLInputElement;
          const setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype,
            'value'
          )!.set!;
          setter.call(input, value);                              // set value
          input.dispatchEvent(new Event('input', { bubbles: true })); // notify React
        })
        .should('have.value', value);
    };

    setNumByLabel(/Anomaly window/i, '3');
    setNumByLabel(/Z threshold/i, '2');

    cy.get('[data-testid="toggle-anomalies"]').click();
    cy.wait('@anomsParams');

    cy.get('[data-testid="anomaly-point"]').should('have.length', 1);
  });
});