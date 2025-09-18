import { useEffect, useState } from "react";
import MetricDailyChart from "./MetricDailyChart";


type MetricDaily = { metric_date: string; source_id: number; metric: string; value: number };
type Source = { id: number; name: string };

export default function MetricDailyCard() {
  const [sources, setSources] = useState<Source[]>([]);
  const [sourceId, setSourceId] = useState<number | null>(null);
  const [rows, setRows] = useState<MetricDaily[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  // load sources
  useEffect(() => {
    fetch("/api/sources")
      .then(r => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then((data: Source[]) => {
        setSources(data);
        if (data.length && sourceId === null) setSourceId(data[0].id); // default to first
      })
      .catch(e => setErr(String(e)));
  }, []);

  // load metrics when sourceId is ready
  useEffect(() => {
    if (sourceId === null) return;
    setLoading(true);
    setErr(null);
    const params = new URLSearchParams({
      metric: "events_total",
      source_id: String(sourceId),
      start_date: "2025-09-15",
      end_date: "2025-09-30",
      limit: "1000",
    });
    fetch("/api/metrics/daily?" + params.toString())
      .then(r => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then(setRows)
      .catch(e => setErr(String(e)))
      .finally(() => setLoading(false));
  }, [sourceId]);

  return (
    <div style={{ padding: 16, border: "1px solid #eee", borderRadius: 8 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 8 }}>
        <h3 style={{ margin: 0, flex: 1 }}>Daily KPIs (events_total)</h3>
        <label>
          Source:&nbsp;
          <select
            value={sourceId ?? ""}
            onChange={(e) => setSourceId(Number(e.target.value))}
            disabled={!sources.length}
          >
            {sources.map(s => (
              <option key={s.id} value={s.id}>{s.name} (#{s.id})</option>
            ))}
          </select>
        </label>
      </div>

      {loading ? (
        <div>Loading…</div>
      ) : err ? (
        <div>Error: {err}</div>
      ) : rows.length === 0 ? (
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
            {rows.length > 0 && <MetricDailyChart rows={rows} />}
          </tbody>
        </table>
      )}
    </div>
  );
}
