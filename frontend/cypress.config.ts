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
  env: {
    API_BASE_URL: 'http://127.0.0.1:8000',
    AUTH_EMAIL: 'demo@example.com',
    AUTH_PASSWORD: 'demo123',
    AUTH_STORAGE_PREFIX: 'sdp_',
  },
  screenshotsFolder: 'cypress/screenshots',
  trashAssetsBeforeRuns: true,
});
