import { useEffect, useMemo, useState } from "react";
import MetricDailyChart, { type ChartPoint } from "./MetricDailyChart";

type MetricDaily = { metric_date: string; source_id: number; metric: string; value: number };
type Source = { id: number; name: string };
type Agg = "sum" | "avg" | "count";

export default function MetricDailyCard() {
  const [sources, setSources] = useState<Source[]>([]);
  const [sourceId, setSourceId] = useState<number | null>(null);

  // filters
  const [metric] = useState("events_total");        // single metric for now
  const [agg, setAgg] = useState<Agg>("sum");       // sum | avg | count
  const [startDate, setStartDate] = useState("2025-09-15");
  const [endDate, setEndDate] = useState("2025-09-30");

  const [rows, setRows] = useState<MetricDaily[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  // Load sources once
  useEffect(() => {
    fetch("/api/sources")
      .then(r => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then((data: Source[]) => {
        setSources(data);
        if (data.length && sourceId === null) setSourceId(data[0].id);
      })
      .catch(e => setErr(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load metrics when filters change
  useEffect(() => {
    if (sourceId === null) return;
    setLoading(true);
    setErr(null);

    const params = new URLSearchParams({
      metric,
      source_id: String(sourceId),
      start_date: startDate,
      end_date: endDate,
      agg,                 // ← NEW
      limit: "2000",
    });

    fetch("/api/metrics/daily?" + params.toString())
      .then(r => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then((data: MetricDaily[]) => setRows(data))
      .catch(e => setErr(String(e)))
      .finally(() => setLoading(false));
  }, [sourceId, metric, agg, startDate, endDate]);

  // Map API rows -> chart points
  const chartData: ChartPoint[] = useMemo(
    () => rows.map(r => ({ date: r.metric_date, value: r.value })),
    [rows]
  );

  const label = useMemo(() => {
    const src = sources.find(s => s.id === sourceId)?.name ?? "—";
    return `Showing ${metric} (${agg}) for ${src} from ${startDate} to ${endDate}`;
  }, [sources, sourceId, metric, agg, startDate, endDate]);

  return (
    <fieldset className="card">
      <legend>Daily KPIs</legend>

      {/* Controls */}
      <div className="controls">
        <div style={{ justifySelf: "end" }}>
          <label>
            Source:&nbsp;
            <select
              value={sourceId ?? ""}
              onChange={(e) => setSourceId(Number(e.target.value))}
              disabled={!sources.length}
            >
              {sources.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} (#{s.id})
                </option>
              ))}
            </select>
          </label>
        </div>

        <div>
          <label>
            Start:&nbsp;
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </label>
        </div>

        <div>
          <label>
            End:&nbsp;
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </label>
        </div>

        <div style={{ justifySelf: "start" }}>
          <label>
            Aggregate:&nbsp;
            <select value={agg} onChange={(e) => setAgg(e.target.value as Agg)}>
              <option value="sum">Sum</option>
              <option value="avg">Average</option>
              <option value="count">Count</option>
            </select>
          </label>
        </div>

        <div style={{ gridColumn: "1 / -1", color: "#666", fontSize: 12, textAlign: "left" }}>
          {label}
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div>Loading…</div>
      ) : err ? (
        <div>Error: {err}</div>
      ) : rows.length === 0 ? (
        <div>No data</div>
      ) : (
        <>
          <table className="data">
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

          <div className="chart" style={{ height: 260, width: "100%" }}>
            <MetricDailyChart data={chartData} />
          </div>
        </>
      )}
    </fieldset>
  );
}
