import { useEffect, useState } from "react";
import type { ReliabilityDetails } from "../components/DetailsDrawer";

export interface UseReliabilityParams {
  sourceName: string;
  metric: string;
}

export function useReliability({ sourceName, metric }: UseReliabilityParams) {
  const [data, setData] = useState<ReliabilityDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sourceName || !metric) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    const fetchReliability = async () => {
      try {
        const params = new URLSearchParams({ source_name: sourceName, metric });
        const response = await fetch(`/api/forecast/reliability?${params.toString()}`);

        if (!response.ok) {
          let message = `Request failed with status ${response.status}`;
          try {
            const body = await response.json();
            message = body?.detail ?? message;
          } catch {
            // ignore JSON parse failure for error payload
          }
          throw new Error(message);
        }

        const payload = (await response.json()) as ReliabilityDetails;
        if (!cancelled) {
          // Accept server-provided score/grade/summary/folds. Be tolerant of extra fields.
          setData(payload);
        }
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
