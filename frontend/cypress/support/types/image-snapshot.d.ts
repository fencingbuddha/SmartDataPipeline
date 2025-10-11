declare module 'cypress-image-snapshot/command' {
  export function addMatchImageSnapshotCommand(options?: any): void;
}
declare module 'cypress-image-snapshot/plugin' {
  const plugin: (on: any, config: any) => any;
  export = plugin;
}
