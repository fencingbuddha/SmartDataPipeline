import { useEffect, useMemo, useState } from "react";
import { getJson } from "../lib/api";
import type { AnomalyPoint, ISODate } from "../types/metrics";

export interface AnomalyParams {
  source_name: string;
  metric: string;
  start_date?: ISODate;
  end_date?: ISODate;
  window?: number;         // rolling window (e.g., 7)
  z_thresh?: number;       // z-threshold (e.g., 2)
}

export function useAnomalies(params: AnomalyParams, enabled = true) {
  const [data, setData] = useState<AnomalyPoint[] | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const stableParams = useMemo(
    () => ({ ...params }),
    [params.source_name, params.metric, params.start_date, params.end_date, params.window, params.z_thresh]
  );

  useEffect(() => {
    if (!enabled) {
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }

    const ctrl = new AbortController();
    setLoading(true);
    setError(null);

    getJson<AnomalyPoint[]>("/api/metrics/anomaly/rolling", stableParams, ctrl.signal)
      .then((rows) => setData(rows))
      .catch((e) => {
        if (e.name !== "AbortError") setError(e as Error);
      })
      .finally(() => setLoading(false));

    return () => ctrl.abort();
  }, [stableParams, enabled]);

  return { data, loading, error };
}
