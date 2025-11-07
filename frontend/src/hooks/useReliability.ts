import { useEffect, useRef, useState } from "react";
import type { ReliabilityDetails } from "../components/DetailsDrawer";
import { getJson } from "../lib/api";

interface ReliabilitySummary { mae?: number; rmse?: number; mape?: number; smape?: number }

function normalizeReliabilityPayload(raw: any): ReliabilityDetails {
  const js = raw?.data ?? raw; // backend returns { ok, data: { avg_* , score } }

  const score = typeof js?.score === "number"
    ? js.score
    : typeof js?.composite_score === "number"
    ? js.composite_score
    : null;

  const summary: ReliabilitySummary | undefined = js?.summary ?? {
    mae: typeof js?.avg_mae === "number" ? js.avg_mae : js?.mae,
    rmse: typeof js?.avg_rmse === "number" ? js.avg_rmse : js?.rmse,
    mape: typeof js?.avg_mape === "number" ? js.avg_mape : js?.mape,
    smape: typeof js?.avg_smape === "number" ? js.avg_smape : js?.smape,
  };

  const folds = Array.isArray(js?.folds)
    ? js.folds
    : Array.isArray(js?.results)
    ? js.results
    : undefined;

  return { score, grade: js?.grade, summary, folds } as ReliabilityDetails;
}

export interface UseReliabilityParams {
  sourceName: string;
  metric: string;
}

export function useReliability({ sourceName, metric }: UseReliabilityParams) {
  const [data, setData] = useState<ReliabilityDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const lastKey = useRef<string>("");

  useEffect(() => {
    if (!sourceName || !metric) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    const key = `${sourceName}|${metric}`;
    lastKey.current = key;

    const fetchReliability = async () => {
      console.debug("useReliability → fetch", { sourceName, metric });
      try {
        const raw = await getJson(
          "/api/forecast/reliability",
          { source_name: sourceName, metric },
        );
        if (cancelled || lastKey.current !== key) return;
        const normalized = normalizeReliabilityPayload(raw);
        setData(normalized);
      } catch (fetchError) {
        if (cancelled) return;
        const message =
          fetchError instanceof Error ? fetchError.message : "failed to load reliability";
        setError(message);
        setData(null);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void fetchReliability();

    return () => {
      cancelled = true;
    };
  }, [sourceName, metric]);

  return { data, loading, error };
}
