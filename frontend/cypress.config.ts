import { defineConfig } from 'cypress';

// use image-diff-js
const getCompareSnapshotsPlugin = require('cypress-image-diff-js/plugin');

export default defineConfig({
  e2e: {
    setupNodeEvents(on, config) {
      getCompareSnapshotsPlugin(on, config);
      return config;
    },
    baseUrl: 'http://localhost:5173',
    specPattern: 'cypress/e2e/**/*.cy.{ts,js}',
    supportFile: 'cypress/support/e2e.ts',
    video: false,
    screenshotOnRunFailure: true,
  },
  screenshotsFolder: 'cypress/screenshots',
  trashAssetsBeforeRuns: true,
});
