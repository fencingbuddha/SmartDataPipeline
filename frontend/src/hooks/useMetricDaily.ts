import { useEffect, useMemo, useState } from "react";
import { getJson } from "../lib/api";
import type { MetricDailyRow, ISODate } from "../types/metrics";

export interface MetricDailyParams {
  source_name: string;
  metric: string;
  start_date?: ISODate;
  end_date?: ISODate;
  agg?: "sum" | "avg" | "count" | "distinct";
}

export function useMetricDaily(params: MetricDailyParams) {
  const [data, setData] = useState<MetricDailyRow[] | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const stableParams = useMemo(() => ({ ...params }), [params.source_name, params.metric, params.start_date, params.end_date, params.agg]);

  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);

    getJson<MetricDailyRow[]>("/api/metrics/daily", stableParams, ctrl.signal)
      .then((rows) => setData(rows))
      .catch((e) => {
        if (e.name !== "AbortError") setError(e as Error);
      })
      .finally(() => setLoading(false));

    return () => ctrl.abort();
  }, [stableParams]);

  return { data, loading, error };
}
