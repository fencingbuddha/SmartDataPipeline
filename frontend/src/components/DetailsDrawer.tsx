import React from "react";

export interface FoldMetric {
  fold: number;
  train_end?: string;   // ISO
  test_start?: string;  // ISO
  test_end?: string;    // ISO
  mae?: number;
  rmse?: number;
  mape?: number;
  smape?: number;
  n?: number;
  calibration_ratio?: number;
  shapiro_p?: number;
}

export interface ReliabilityDetails {
  score?: number;
  grade?: "A"|"B"|"C"|"D"|"N/A";
  summary?: { mae?: number; rmse?: number; mape?: number; smape?: number };
  folds?: FoldMetric[];
}

export interface DetailsDrawerProps {
  open: boolean;
  onClose: () => void;
  details?: ReliabilityDetails | null;
}

export const DetailsDrawer: React.FC<DetailsDrawerProps> = ({ open, onClose, details }) => {
  return (
    <div
      role="dialog"
      aria-modal="true"
      className={`fixed inset-0 z-50 transition ${open ? "pointer-events-auto" : "pointer-events-none"}`}
      data-testid="rel-drawer"
    >
      {/* backdrop */}
      <div
        className={`absolute inset-0 bg-black/40 transition-opacity ${open ? "opacity-100" : "opacity-0"}`}
        onClick={onClose}
      />
      {/* panel */}
      <div
        className={`absolute right-0 top-0 h-full w-full max-w-xl bg-white shadow-xl transition-transform ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="p-4 border-b flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Forecast Reliability Details</h2>
            <p className="text-sm text-gray-500">
              Composite score {details?.score != null ? Math.round(details.score) : "—"} · Grade {details?.grade ?? "—"}
            </p>
          </div>
          <button className="rounded px-3 py-1 text-sm bg-gray-100" onClick={onClose}>Close</button>
        </div>

        {/* summary cards */}
        <div className="grid grid-cols-2 gap-3 p-4">
          {(["mae","rmse","mape","smape"] as const).map(k => (
            <div key={k} className="rounded-2xl border p-3">
              <div className="text-xs uppercase tracking-wide text-gray-500">{k}</div>
              <div className="text-lg font-semibold" data-testid={`rel-sum-${k}`}>
                {details?.summary?.[k] != null ? Number(details!.summary![k]!).toFixed(3) : "—"}
              </div>
            </div>
          ))}
        </div>

        {/* folds table */}
        <div className="p-4">
          <div className="text-sm font-medium mb-2">Backtesting Folds</div>
          <div className="overflow-auto border rounded-2xl">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {["fold","test_start","test_end","n","mae","rmse","mape","smape","calib","shapiro_p"].map(h => (
                    <th key={h} className="px-3 py-2 text-left font-semibold">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody data-testid="rel-folds">
                {(details?.folds ?? []).map(r => (
                  <tr key={r.fold} className="odd:bg-white even:bg-gray-50">
                    <td className="px-3 py-2">{r.fold}</td>
                    <td className="px-3 py-2">{r.test_start ?? "—"}</td>
                    <td className="px-3 py-2">{r.test_end ?? "—"}</td>
                    <td className="px-3 py-2">{r.n ?? "—"}</td>
                    <td className="px-3 py-2">{r.mae?.toFixed(3) ?? "—"}</td>
                    <td className="px-3 py-2">{r.rmse?.toFixed(3) ?? "—"}</td>
                    <td className="px-3 py-2">{r.mape?.toFixed(2) ?? "—"}</td>
                    <td className="px-3 py-2">{r.smape?.toFixed(2) ?? "—"}</td>
                    <td className="px-3 py-2">{r.calibration_ratio?.toFixed(2) ?? "—"}</td>
                    <td className="px-3 py-2">{r.shapiro_p?.toFixed(3) ?? "—"}</td>
                  </tr>
                ))}
                {(!details?.folds || details.folds.length === 0) && (
                  <tr>
                    <td className="px-3 py-3 text-gray-500" colSpan={10}>No fold metrics available</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};