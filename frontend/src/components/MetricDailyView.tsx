import React from "react";

export type MetricDailyViewProps = {
  // ordered content slots
  filters: React.ReactNode;
  tiles: React.ReactNode;
  table: React.ReactNode;
  chart: React.ReactNode;

  // lightweight UX bits
  isLoading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
  onReset?: () => void;

  showEmptyState?: boolean;
  emptyStateText?: string;
};

export default function MetricDailyView({
  filters,
  tiles,
  table,
  chart,
  isLoading = false,
  error = null,
  onRefresh,
  onReset,
  showEmptyState = false,
  emptyStateText = "No data for the selected Source/Metric/Date range. Try widening the date window or choosing a different source.",
}: MetricDailyViewProps) {
  return (
    <section aria-label="Metric daily dashboard" className="space-y-3">
      {/* Controls */}
      <div className="flex items-center gap-2">
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            className="btn btn-primary focus-visible:outline-2 focus-visible:outline-offset-2"
            aria-label="Refresh data"
          >
            Refresh
          </button>
        )}
        {onReset && (
          <button
            type="button"
            onClick={onReset}
            className="btn btn-secondary focus-visible:outline-2 focus-visible:outline-offset-2"
            aria-label="Reset filters"
          >
            Reset
          </button>
        )}
        {isLoading && <span aria-live="polite" className="ml-auto text-sm">Loading…</span>}
      </div>

      {/* A11y live region for async errors */}
      <div aria-live="polite" role={error ? "alert" : undefined} className="min-h-[1.25rem]">
        {error && <div className="text-red-600" data-testid="error-banner">{error}</div>}
      </div>

      {/* Figma order: Filters → Tiles → Table → Chart */}
      <div data-testid="filters-section">{filters}</div>
      <div data-testid="tiles-section">{tiles}</div>
      <div data-testid="table-section">{table}</div>

      <div data-testid="chart-section">
        {showEmptyState ? (
          <div
            data-testid="empty-state"
            role="status"
            aria-live="polite"
            className="sd-mt-2 sd-text-sm sd-text-neutral-600"
          >
            {emptyStateText}
          </div>
        ) : (
          chart
        )}
      </div>
    </section>
  );
}