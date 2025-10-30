import React from "react";

export type ReliabilityGrade = "A" | "B" | "C" | "D" | "N/A";

export interface ReliabilityBadgeProps {
  score?: number | null;            // 0–100 (higher is better)
  grade?: ReliabilityGrade;         // derived server-side (preferred) or client-side
  loading?: boolean;
  error?: string | null;
  onClick?: () => void;             // opens the details drawer
  compact?: boolean;                // small badge for table rows/cards
}

function gradeFromScore(score?: number | null): ReliabilityGrade {
  if (score == null || Number.isNaN(score)) return "N/A";
  if (score >= 85) return "A";
  if (score >= 70) return "B";
  if (score >= 55) return "C";
  return "D";
}

export const ReliabilityBadge: React.FC<ReliabilityBadgeProps> = ({
  score,
  grade,
  loading,
  error,
  onClick,
  compact,
}) => {
  if (loading) {
    return (
      <span
        className={`inline-flex items-center rounded-2xl px-2 py-1 text-xs bg-gray-200`}
        data-testid="rel-badge-loading"
        aria-live="polite"
      >
        reliability: loading…
      </span>
    );
  }
  if (error) {
    return (
      <button
        type="button"
        className={`inline-flex items-center rounded-2xl px-2 py-1 text-xs bg-red-100 text-red-700`}
        onClick={onClick}
        data-testid="rel-badge-error"
        title={error}
      >
        reliability: error
      </button>
    );
  }

  const resolvedGrade = grade ?? gradeFromScore(score);
  const tone =
    resolvedGrade === "A"
      ? "bg-emerald-100 text-emerald-800"
      : resolvedGrade === "B"
      ? "bg-lime-100 text-lime-800"
      : resolvedGrade === "C"
      ? "bg-amber-100 text-amber-800"
      : resolvedGrade === "D"
      ? "bg-red-100 text-red-800"
      : "bg-gray-200 text-gray-700";

  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center rounded-2xl ${compact ? "px-2 py-0.5 text-[10px]" : "px-3 py-1 text-xs"} ${tone}`}
      style={{ columnGap: compact ? 6 : 10 }}
      data-testid="rel-badge"
      aria-label={`forecast reliability ${resolvedGrade}${score != null ? `, score ${Math.round(score)}` : ""}`}
    >
      <span style={{ fontWeight: 600 }}>Reliability:</span>
      <span style={{ fontWeight: 700 }} data-testid="rel-grade">
        {resolvedGrade}
      </span>
      {score != null && (
        <span style={{ fontWeight: 700 }} data-testid="rel-score">
          /{Math.round(score)}
        </span>
      )}
    </button>
  );
};
