/// <reference types="node" />
import process from 'node:process';
import { config as loadEnv } from 'dotenv';
import { defineConfig } from 'cypress';
import getCompareSnapshotsPlugin from 'cypress-image-diff-js/plugin';

loadEnv({ path: '.env.cypress', override: true });

const {
  VITE_TEST_API_BASE,
  VITE_TEST_AUTH_EMAIL,
  VITE_TEST_AUTH_PASSWORD,
  VITE_AUTH_STORAGE_PREFIX,
} = process.env;

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
      VITE_TEST_API_BASE,
      VITE_TEST_AUTH_EMAIL,
      VITE_TEST_AUTH_PASSWORD,
      VITE_AUTH_STORAGE_PREFIX: VITE_AUTH_STORAGE_PREFIX ?? 'sdp_',
    },
  },
  screenshotsFolder: 'cypress/screenshots',
  trashAssetsBeforeRuns: true,
});
