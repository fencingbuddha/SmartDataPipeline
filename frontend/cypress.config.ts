/// <reference types="node" />
import process from 'node:process';
import 'dotenv/config'; // <-- loads frontend/.env.cypress for Cypress runs
import { defineConfig } from 'cypress';
import getCompareSnapshotsPlugin from 'cypress-image-diff-js/plugin';

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
    env: {
      VITE_TEST_API_BASE: process.env.VITE_TEST_API_BASE,
      VITE_TEST_AUTH_EMAIL: process.env.VITE_TEST_AUTH_EMAIL,
      VITE_TEST_AUTH_PASSWORD: process.env.VITE_TEST_AUTH_PASSWORD,
      VITE_AUTH_STORAGE_PREFIX: process.env.VITE_AUTH_STORAGE_PREFIX ?? 'sdp_',
    },
  },
  screenshotsFolder: 'cypress/screenshots',
  trashAssetsBeforeRuns: true,
});
