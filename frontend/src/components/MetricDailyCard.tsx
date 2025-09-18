import { useEffect, useState } from "react";

type MetricDaily = {
  metric_date: string;
  source_id: number;
  metric: string;
  value: number;
};

export default function MetricDailyCard() {
  const [rows, setRows] = useState<MetricDaily[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams({
      metric: "events_total",
      source_id: "1",              // TODO: later wire a dropdown
      start_date: "2025-09-15",
      end_date: "2025-09-30",
      limit: "1000",
    });

    fetch("/api/metrics/daily?" + params.toString())
      .then(r => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then(setRows)
      .catch(e => setErr(String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div>Loading…</div>;
  if (err) return <div>Error: {err}</div>;

  return (
    <div style={{ padding: 16, border: "1px solid #eee", borderRadius: 8 }}>
      <h3 style={{ marginTop: 0 }}>Daily KPIs (events_total, src=1)</h3>
      {rows.length === 0 ? (
        <div>No data</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>Date</th>
              <th style={{ textAlign: "right" }}>Value</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={`${r.metric_date}-${r.source_id}-${r.metric}`}>
                <td>{r.metric_date}</td>
                <td style={{ textAlign: "right" }}>{r.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
