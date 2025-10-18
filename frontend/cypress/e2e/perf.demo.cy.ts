// P95 time-to-ready ≤ 5000ms
function p95(arr: number[]) {
  const a = [...arr].sort((x, y) => x - y);
  const i = Math.ceil(a.length * 0.95) - 1;
  return a[Math.max(0, Math.min(a.length - 1, i))];
}

describe("Demo dashboard perf gate (@perf)", () => {
  it("P95 time-to-ready ≤ 5000ms", () => {
    const runs = 20;
    const timings: number[] = [];
    for (let i = 0; i < runs; i++) {
      const t0 = performance.now();
      cy.visit("/");
      cy.get('[data-testid="filter-source"]').select("demo-source");
      cy.get('[data-testid="filter-metric"]').select("events_total");
      cy.get('[data-testid="btn-run"]').click();
      cy.get('[data-testid="chart"]').should("be.visible");
      cy.then(() => timings.push(performance.now() - t0));
    }
    cy.then(() => {
      const val = p95(timings);
      cy.log(`P95(ms)=${Math.round(val)}`);
      expect(val, "P95 time-to-ready").to.be.lte(5000);
    });
  });
});
