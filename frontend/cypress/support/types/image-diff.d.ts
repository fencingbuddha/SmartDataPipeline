// Minimal shims so TypeScript is happy

declare module 'cypress-image-diff-js' {
  export function compareSnapshotCommand(options?: {
    failureThreshold?: number;
    failureThresholdType?: 'percent' | 'pixel';
    capture?: 'viewport' | 'fullPage' | 'runner';
  }): void;
}

declare module 'cypress-image-diff-js/plugin' {
  const plugin: (on: any, config: any) => any;
  export = plugin;
}

// add the Chainable signature so VS Code knows cy.compareSnapshot(...)
declare namespace Cypress {
  interface Chainable {
    compareSnapshot(name: string, threshold?: number): Chainable<void>;
  }
}
