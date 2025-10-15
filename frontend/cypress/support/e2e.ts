import '@testing-library/cypress/add-commands';
import './commands';

// Register cy.compareSnapshot(...) using the package main export.
// This works whether the package exports a function or { compareSnapshotCommand }.
const mod = require('cypress-image-diff-js');
const register =
  (typeof mod === 'function' ? mod : mod?.compareSnapshotCommand) ||
  (() => { throw new Error('cypress-image-diff-js: register fn not found'); });
// NOTE: official docs show CommonJS
const compareSnapshotCommand = require('cypress-image-diff-js/command');
compareSnapshotCommand();


register({
  failureThreshold: 0.02,
  failureThresholdType: 'percent',
  capture: 'viewport',
});
