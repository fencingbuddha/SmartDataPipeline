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
      API_BASE_URL: process.env.API_BASE_URL,
      AUTH_EMAIL: process.env.AUTH_EMAIL,
      AUTH_PASSWORD: process.env.AUTH_PASSWORD,
      AUTH_STORAGE_PREFIX: process.env.AUTH_STORAGE_PREFIX ?? 'sdp_',
    },
  },
  screenshotsFolder: 'cypress/screenshots',
  trashAssetsBeforeRuns: true,
});