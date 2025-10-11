/// <reference types="cypress" />
import type { Interception } from 'cypress/types/net-stubbing';

const API_BASE = Cypress.env('API_BASE') || 'http://127.0.0.1:8000';

/** Find the input for a given label (works even if label/for isn’t wired) */
const inputByLabel = (labelRx: RegExp) =>
  cy.contains('label', labelRx).then(($label) => {
    const id = $label.attr('for');
    if (id) return cy.get(`#${id}`);
    return cy.wrap($label).parent().find('input');
  });

/** Set a React-controlled number input (avoid “37” etc.) */
const setNumByLabel = (labelRx: RegExp, value: string) => {
  inputByLabel(labelRx)
    .then(($el) => {
      const input = $el[0] as HTMLInputElement;
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        'value'
      )!.set!;
      setter.call(input, value);
      input.dispatchEvent(new Event('input', { bubbles: true }));
    })
    .should('have.value', value);
};

describe('Dashboard anomaly overlay (enhanced)', () => {
  const visitDash = () => cy.visit('/');

  it('shows overlay markers only when the checkbox is ON (Apply required)', () => {
    // Series data
    cy.intercept('GET', `${API_BASE}/api/metrics/daily*`, {
      statusCode: 200,
      body: [
        { metric_date: '2025-10-01', value: 1 },
        { metric_date: '2025-10-02', value: 2 },
        { metric_date: '2025-10-03', value: 12 },
      ],
    }).as('daily');

    // 🔐 Explicit anomaly matcher + guaranteed outlier reply
    cy.intercept('GET', `${API_BASE}/api/metrics/anomaly/rolling*`, (req) => {
      req.alias = 'anoms';
      req.reply([
        { date: '2025-10-03', value: 12, is_outlier: true, z: 3.2 },
      ]);
    });

    visitDash();
    cy.wait('@daily');

    // Initially present & unchecked, and no markers
    cy.findByLabelText(/Show anomalies/i).should('exist').and('not.be.checked');
    cy.get('[data-testid="anomaly-point"]').should('not.exist');

    // Apply → then enable overlay
    cy.findByRole('button', { name: /apply/i }).click();
    cy.findByLabelText(/Show anomalies/i).check({ force: true });

    // Request will be stubbed by the intercept above and draw a marker
    cy.wait('@anoms');
    cy.get('[data-testid="anomaly-point"]', { timeout: 10000 })
      .should('have.length.at.least', 1);

    // Visual snapshots
    cy.compareSnapshot('anomaly-overlay-on', 0.02);

    // Turn off and verify cleared
    cy.findByLabelText(/Show anomalies/i).uncheck({ force: true });
    cy.get('[data-testid="anomaly-point"]').should('not.exist');
    cy.compareSnapshot('anomaly-overlay-off', 0.02);
  });

  it('disables the checkbox and shows empty state when no data', () => {
    cy.intercept('GET', `${API_BASE}/api/metrics/daily*`, {
      statusCode: 200,
      body: [],
    }).as('dailyEmpty');

    visitDash();
    cy.wait('@dailyEmpty');

    cy.contains(/No data for this selection/i).should('be.visible');
    cy.findByLabelText(/Show anomalies/i).should('be.disabled');

    // After Apply it should remain disabled if still no data
    cy.findByRole('button', { name: /apply/i }).click();
    cy.findByLabelText(/Show anomalies/i).should('be.disabled');
  });

  it('passes chosen parameters (window, z) to API after Apply', () => {
    cy.intercept('GET', `${API_BASE}/api/metrics/daily*`, {
      statusCode: 200,
      body: [
        { metric_date: '2025-10-01', value: 1 },
        { metric_date: '2025-10-02', value: 2 },
        { metric_date: '2025-10-03', value: 12 },
      ],
    }).as('dailyOk');

    // Assert params AND reply with an outlier so UI renders a marker
    cy.intercept('GET', `${API_BASE}/api/metrics/anomaly/rolling*`, (req) => {
      expect(req.query.window, 'window').to.eq('3'); // from the inputs we set
      const zParam = (req.query as any).z ?? (req.query as any).z_thresh;
      expect(zParam, 'z or z_thresh').to.eq('2');
      req.alias = 'anomsParams';
      req.reply([
        { date: '2025-10-03', value: 12, is_outlier: true, z: 3.2 },
      ]);
    });

    visitDash();
    cy.wait('@dailyOk');

    // Set inputs reliably
    setNumByLabel(/Anomaly window/i, '3');
    setNumByLabel(/Z threshold/i, '2');

    // Apply first; then enable overlay
    cy.findByRole('button', { name: /apply/i }).click();
    cy.findByLabelText(/Show anomalies/i).check({ force: true });

    // Confirm we hit the intercept and UI renders a marker
    cy.wait('@anomsParams');
    cy.get('[data-testid="anomaly-point"]', { timeout: 10000 })
      .should('have.length.at.least', 1);
  });

  it.skip('shows an error banner when the daily API fails (align text later)', () => {
    cy.intercept('GET', `${API_BASE}/api/metrics/daily*`, {
      statusCode: 500,
      body: { detail: 'server error' },
    }).as('dailyErr');

    visitDash();
    cy.wait('@dailyErr');

    // TODO: replace with exact banner text/role, then remove .skip
    cy.contains(/failed|error|unable/i).should('be.visible');
  });
});
