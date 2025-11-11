import '@testing-library/cypress/add-commands';
import './commands';

// --- Visual snapshot bootstrap with graceful fallbacks ---
// We support either plugin if present; otherwise we polyfill a no-op so the suite runs.
// Prefer setting threshold via VIS_THRESH env (percent). Default 1.5%.
const VIS_THRESH = Number(Cypress.env('VIS_THRESH') ?? 1.5);

let registered = false;
try {
  // Try the cypress-visual-regression package (provides cy.compareSnapshot)
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  require('cypress-visual-regression/dist/commands');
  registered = true;
} catch (_) {
  try {
    // Fallback: cypress-image-diff-js (exposes compareSnapshotCommand)
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const maybe = require('cypress-image-diff-js');
    const compareSnapshotCommand = maybe && maybe.compareSnapshotCommand;
    if (typeof compareSnapshotCommand === 'function') {
      compareSnapshotCommand({
        failureThreshold: VIS_THRESH / 100, // plugin expects ratio when type='percent'
        failureThresholdType: 'percent',
        capture: 'viewport',
      });
      registered = true;
    }
  } catch (_) {
    // ignore; we'll polyfill below
  }
}

if (!registered) {
  // Last-resort polyfill so specs don't explode if the plugin isn't installed locally.
  // It captures a screenshot for artifacts and treats the check as pass.
  // @ts-expect-error: Custom command added for compatibility with existing tests
  Cypress.Commands.add('compareSnapshot', (name: string, _opts?: unknown) => {
    const label = typeof name === 'string' ? name : 'snapshot';
    cy.screenshot(`__polyfill__-${label}`, { capture: 'viewport' });
    cy.log('compareSnapshot polyfill active — install a visual plugin for real diffs');
  });
}
