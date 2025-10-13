import { useEffect, useMemo, useState } from "react";
import { getJson } from "../lib/api";
import type { ForecastPoint, ISODate } from "../types/metrics";

export interface ForecastParams {
  source_name: string;
  metric: string;
  start_date?: ISODate; // used to align/clip
  end_date?: ISODate;   // used to align/clip
}

export function useForecast(params: ForecastParams, enabled = true) {
  const [data, setData] = useState<ForecastPoint[] | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const stableParams = useMemo(
    () => ({ ...params }),
    [params.source_name, params.metric, params.start_date, params.end_date]
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

    getJson<ForecastPoint[]>("/api/forecast/daily", stableParams, ctrl.signal)
      .then((rows) => setData(rows))
      .catch((e) => {
        if (e.name !== "AbortError") setError(e as Error);
      })
      .finally(() => setLoading(false));

    return () => ctrl.abort();
  }, [stableParams, enabled]);

  return { data, loading, error };
}
