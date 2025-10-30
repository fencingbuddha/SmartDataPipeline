import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReliabilityGrade } from "./ReliabilityBadge";

const EDGE_GAP = 16;

export interface FoldMetric {
  fold: number;
  train_end?: string;
  test_start?: string;
  test_end?: string;
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
  grade?: "A" | "B" | "C" | "D" | "N/A";
  summary?: {
    mae?: number;
    rmse?: number;
    mape?: number;
    smape?: number;
    calibration_ratio?: number;
  };
  folds?: FoldMetric[];
  meta?: { folds?: number; horizon?: number; window_n?: number };
}

export interface DetailsDrawerProps {
  open: boolean;
  onClose: () => void;
  details?: ReliabilityDetails | null;
}

const clamp = (value: number, min: number, max: number) =>
  Math.min(Math.max(value, min), max);

const gradeFromScore = (score?: number | null): ReliabilityGrade => {
  if (score == null || Number.isNaN(score)) return "N/A";
  if (score >= 85) return "A";
  if (score >= 70) return "B";
  if (score >= 55) return "C";
  return "D";
};

export const DetailsDrawer: React.FC<DetailsDrawerProps> = ({ open, onClose, details }) => {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const dragOffsetRef = useRef({ x: 0, y: 0 });
  const draggingRef = useRef(false);
  const pointerIdRef = useRef<number | null>(null);
  const [position, setPosition] = useState<{ x: number; y: number }>({
    x: EDGE_GAP * 5,
    y: EDGE_GAP * 5,
  });

  // Close on ESC
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Center the modal the first time it opens.
  useEffect(() => {
    if (!open) return;
    const frame = dialogRef.current;
    if (!frame || typeof window === "undefined") return;
    const rect = frame.getBoundingClientRect();
    const maxX = window.innerWidth - rect.width - EDGE_GAP;
    const maxY = window.innerHeight - rect.height - EDGE_GAP;
    const centeredX =
      maxX <= EDGE_GAP
        ? EDGE_GAP
        : clamp((window.innerWidth - rect.width) / 2, EDGE_GAP, maxX);
    const centeredY =
      maxY <= EDGE_GAP
        ? EDGE_GAP
        : clamp((window.innerHeight - rect.height) / 2, EDGE_GAP, maxY);
    setPosition({ x: centeredX, y: centeredY });
  }, [open]);

  const applyPosition = useCallback((clientX: number, clientY: number) => {
    const { x: offsetX, y: offsetY } = dragOffsetRef.current;
    let nextX = clientX - offsetX;
    let nextY = clientY - offsetY;

    if (typeof window !== "undefined") {
      const frame = dialogRef.current;
      if (frame) {
        const rect = frame.getBoundingClientRect();
        const maxX = window.innerWidth - rect.width - EDGE_GAP;
        const maxY = window.innerHeight - rect.height - EDGE_GAP;
        nextX = clamp(nextX, EDGE_GAP, Math.max(EDGE_GAP, maxX));
        nextY = clamp(nextY, EDGE_GAP, Math.max(EDGE_GAP, maxY));
      }
    }

    setPosition({ x: nextX, y: nextY });
  }, []);

  const handlePointerMove = useCallback(
    (event: React.PointerEvent<Element>) => {
      if (!draggingRef.current) return;
      event.preventDefault();
      applyPosition(event.clientX, event.clientY);
    },
    [applyPosition],
  );

  const endDrag = useCallback(
    (event?: React.PointerEvent<Element>) => {
      if (!draggingRef.current) return;
      draggingRef.current = false;

      if (event) {
        applyPosition(event.clientX, event.clientY);
      }

      const frame = dialogRef.current;
      if (
        frame &&
        pointerIdRef.current != null &&
        typeof frame.releasePointerCapture === "function" &&
        frame.hasPointerCapture?.(pointerIdRef.current)
      ) {
        try {
          frame.releasePointerCapture(pointerIdRef.current);
        } catch {
          // ignore release errors
        }
      }
      pointerIdRef.current = null;
    },
    [applyPosition],
  );

  const handlePointerUp = useCallback(
    (event: React.PointerEvent<Element>) => {
      endDrag(event);
    },
    [endDrag],
  );

  const handlePointerCancel = useCallback(() => {
    endDrag();
  }, [endDrag]);

  const handlePointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (event.button !== 0) return;
      const target = event.target as HTMLElement | null;
      if (target && target.closest("button")) return;

      const frame = dialogRef.current;
      if (!frame) return;

      const rect = frame.getBoundingClientRect();
      dragOffsetRef.current = {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
      };

      draggingRef.current = true;
      event.preventDefault();

      pointerIdRef.current = event.pointerId;
      if (typeof frame.setPointerCapture === "function") {
        try {
          frame.setPointerCapture(event.pointerId);
        } catch {
          // ignore capture errors
        }
      }
    },
    [],
  );

  useEffect(() => {
    if (open) return;
    const frame = dialogRef.current;
    if (
      frame &&
      pointerIdRef.current != null &&
      typeof frame.releasePointerCapture === "function" &&
      frame.hasPointerCapture?.(pointerIdRef.current)
    ) {
      try {
        frame.releasePointerCapture(pointerIdRef.current);
      } catch {
        // ignore release errors
      }
    }
    draggingRef.current = false;
    pointerIdRef.current = null;
  }, [open]);

  const shellStyle = useMemo<React.CSSProperties>(() => {
    return {
      position: "fixed",
      top: position.y,
      left: position.x,
      width: "min(95vw, 520px)",
      maxHeight: "min(90vh, 640px)",
      background:
        "linear-gradient(185deg, rgba(45, 65, 112, 0.98) 0%, rgba(20, 29, 52, 0.98) 65%, rgba(14, 20, 36, 0.95) 100%)",
      borderRadius: "var(--sd-radius-2)",
      border: "2px solid rgba(79, 124, 255, 0.45)",
      boxShadow: "0 22px 45px rgba(11, 20, 40, 0.55), 0 0 0 1px rgba(15, 70, 180, 0.18)",
      color: "var(--sd-color-text)",
    };
  }, [position]);

  const score = details?.score != null ? Math.round(details.score) : null;
  const grade = details?.grade ?? gradeFromScore(details?.score);
  const summary = details?.summary ?? {};
  const foldCount = details?.folds?.length ?? details?.meta?.folds ?? "—";
  const horizon = details?.meta?.horizon ?? "—";

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[1000] relative" data-testid="rel-drawer">
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Forecast Reliability Details"
        className="pointer-events-auto flex flex-col"
        style={shellStyle}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerCancel}
        onPointerLeave={handlePointerCancel}
      >
        <div
          className="px-8 pt-4 pb-5 flex items-center cursor-move select-none"
          style={{
            borderBottom: "1px solid rgba(79, 124, 255, 0.2)",
            background: "linear-gradient(180deg, rgba(79, 124, 255, 0.18) 0%, rgba(24, 32, 51, 0) 100%)",
            marginBottom: "12px",
          }}
          onPointerDown={handlePointerDown}
        >
          <div style={{ marginRight: "auto", paddingLeft: 8 }}>
            <h2 className="text-base font-semibold">Forecast Reliability</h2>
            <p className="text-sm sd-muted">
              Composite score {score ?? "—"} · Grade {grade}
            </p>
          </div>
          <button
            onClick={onClose}
            className="px-3 py-1 text-sm font-semibold cursor-pointer select-auto"
            style={{
              borderRadius: "var(--sd-radius-1)",
              border: "1px solid rgba(79, 124, 255, 0.45)",
              background: "linear-gradient(180deg, rgba(12, 18, 34, 0.95) 0%, rgba(8, 12, 22, 0.95) 100%)",
              color: "rgba(230, 236, 255, 0.92)",
              boxShadow: "0 4px 14px rgba(9, 14, 27, 0.45)",
              marginLeft: "32px",
            }}
          >
            Close
          </button>
        </div>

        <div className="flex-1 overflow-auto px-6 py-6 space-y-6">
          <div style={{ padding: "0 18px" }} />

          <div style={{ padding: "0 18px" }}>
            <table
              className="w-full text-sm"
              style={{
                borderTop: "1px solid rgba(79, 124, 255, 0.25)",
                borderBottom: "1px solid rgba(79, 124, 255, 0.25)",
                padding: "12px 0",
              }}
            >
              <tbody>
                <tr className="border-b">
                  <td className="py-2 pr-3" style={{ color: "rgba(188, 205, 255, 0.75)" }}>
                    Folds
                  </td>
                  <td className="py-2 text-right font-medium">{foldCount}</td>
                </tr>
                <tr className="border-b">
                  <td className="py-2 pr-3" style={{ color: "rgba(188, 205, 255, 0.75)" }}>
                    Horizon
                  </td>
                  <td className="py-2 text-right font-medium">
                    {typeof horizon === "number" ? horizon.toFixed(2) : horizon}
                  </td>
                </tr>
                <tr className="border-b">
                  <td className="py-2 pr-3" style={{ color: "rgba(188, 205, 255, 0.75)" }}>
                    MAE
                  </td>
                  <td className="py-2 text-right font-medium">
                    {typeof summary.mae === "number" ? summary.mae.toFixed(3) : "—"}
                  </td>
                </tr>
                <tr className="border-b">
                  <td className="py-2 pr-3" style={{ color: "rgba(188, 205, 255, 0.75)" }}>
                    RMSE
                  </td>
                  <td className="py-2 text-right font-medium">
                    {typeof summary.rmse === "number"
                      ? summary.rmse.toLocaleString(undefined, { maximumFractionDigits: 3 })
                      : "—"}
                  </td>
                </tr>
                <tr className="border-b">
                  <td className="py-2 pr-3" style={{ color: "rgba(188, 205, 255, 0.75)" }}>
                    MAPE
                  </td>
                  <td className="py-2 text-right font-medium">
                    {typeof summary.mape === "number" ? `${summary.mape.toFixed(2)}%` : "—"}
                  </td>
                </tr>
                <tr className="border-b">
                  <td className="py-2 pr-3" style={{ color: "rgba(188, 205, 255, 0.75)" }}>
                    sMAPE
                  </td>
                  <td className="py-2 text-right font-medium">
                    {typeof summary.smape === "number" ? `${summary.smape.toFixed(2)}%` : "—"}
                  </td>
                </tr>
                <tr className="border-b">
                  <td className="py-2 pr-3" style={{ color: "rgba(188, 205, 255, 0.75)" }}>
                    RMSE/σ
                  </td>
                  <td className="py-2 text-right font-medium">
                    {typeof summary.rmse === "number" && typeof summary.mae === "number"
                      ? (summary.rmse / summary.mae).toFixed(2)
                      : "—"}
                  </td>
                </tr>
                <tr>
                  <td className="py-2 pr-3" style={{ color: "rgba(188, 205, 255, 0.75)" }}>
                    Calibration Ratio p
                  </td>
                  <td className="py-2 text-right font-medium">
                    {typeof summary.calibration_ratio === "number"
                      ? summary.calibration_ratio.toFixed(2)
                      : "—"}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div style={{ padding: "0 18px" }}>
            <div className="text-sm font-medium mb-3" style={{ paddingLeft: 4 }}>
              Fold Metrics
            </div>
            <div
              className="overflow-auto rounded-2xl max-h-72"
              style={{
                border: "1px solid rgba(79, 124, 255, 0.25)",
                boxShadow: "inset 0 0 0 1px rgba(12, 22, 42, 0.45)",
                background: "rgba(8, 14, 26, 0.55)",
                padding: "10px 16px 16px",
              }}
            >
              <table className="min-w-full text-sm" style={{ borderSpacing: 0, borderCollapse: "separate" }}>
                <thead
                  style={{
                    background:
                      "linear-gradient(180deg, rgba(79, 124, 255, 0.18) 0%, rgba(29, 43, 76, 0.25) 100%)",
                    color: "rgba(215, 225, 255, 0.85)",
                  }}
                >
                  <tr>
                    {["fold", "test_start", "test_end", "n", "mae", "rmse", "mape", "smape", "calib", "shapiro_p"].map(
                      (header) => (
                        <th key={header} className="px-3 py-2 text-left font-semibold">
                          {header}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody data-testid="rel-folds">
                  {(details?.folds ?? []).map((row, index) => (
                    <tr
                      key={row.fold}
                      style={{
                        background:
                          index % 2 === 0
                            ? "rgba(60, 86, 153, 0.22)"
                            : "rgba(30, 44, 76, 0.18)",
                        color: "rgba(228, 234, 255, 0.92)",
                      }}
                    >
                      <td className="px-3 py-2">{row.fold}</td>
                      <td className="px-3 py-2">{row.test_start ?? "—"}</td>
                      <td className="px-3 py-2">{row.test_end ?? "—"}</td>
                      <td className="px-3 py-2">{row.n ?? "—"}</td>
                      <td className="px-3 py-2">
                        {typeof row.mae === "number" ? row.mae.toFixed(3) : "—"}
                      </td>
                      <td className="px-3 py-2">
                        {typeof row.rmse === "number" ? row.rmse.toFixed(3) : "—"}
                      </td>
                      <td className="px-3 py-2">
                        {typeof row.mape === "number" ? row.mape.toFixed(2) : "—"}
                      </td>
                      <td className="px-3 py-2">
                        {typeof row.smape === "number" ? row.smape.toFixed(2) : "—"}
                      </td>
                      <td className="px-3 py-2">
                        {typeof row.calibration_ratio === "number" ? row.calibration_ratio.toFixed(2) : "—"}
                      </td>
                      <td className="px-3 py-2">
                        {typeof row.shapiro_p === "number" ? row.shapiro_p.toFixed(3) : "—"}
                      </td>
                    </tr>
                  ))}
                  {(!details?.folds || details.folds.length === 0) && (
                    <tr>
                      <td className="px-3 py-3 sd-muted" colSpan={10}>
                        No fold metrics available
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div style={{ padding: "0 18px" }}>
            <div
              className="text-center text-sm border-t pt-4 pb-1"
              style={{
                borderColor: "rgba(79, 124, 255, 0.2)",
                color: "rgba(182, 200, 255, 0.75)",
              }}
            >
              Lower error & stable folds →{" "}
              <span className="font-medium" style={{ color: "rgba(236, 242, 255, 0.95)" }}>
                Higher reliability
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
