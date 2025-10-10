import { useEffect, useMemo, useState } from "react";
import MetricDailyChart from "./MetricDailyChart";

/**
 * KPI card with filters, CSV export, and configurable anomaly overlay.
 * - Sources -> /api/sources
 * - Metrics per source -> /api/metrics/names?source_name=...
 * - Daily series -> /api/metrics/daily
 * - Anomalies:
 *     - Rolling Z -> /api/metrics/anomaly/rolling?window=&z_thresh=
 *     - Isolation Forest -> /api/metrics/anomaly/iforest?contamination=
 * - UI params: window, z-threshold, algorithm (rolling|iforest)
 * - Graceful loading/empty/error states
 * - Toggle disabled when no data or loading; overlay cleared on filter changes
 */

type Row = {
  metric_date?: string; date?: string; day?: string;
  source_id?: number | string; source?: string;
  metric?: string; name?: string;
  value_sum?: number; sum?: number; total?: number; value?: number;
  value_avg?: number; avg?: number; mean?: number; average?: number;
  value_count?: number; count?: number; rows?: number; n?: number;
  value_distinct?: number; distinct?: number; unique?: number;
};

type Source = { id: number | string; name: string };
type AnomPoint = { date: string; value: number; z?: number };

type ForecastPoint = { date: string; yhat: number };
const FC_CACHE = new Map<string, ForecastPoint[]>();

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";
const METRIC_SUGGESTIONS = ["events_total", "errors_total", "revenue", "signups", "sessions"];

export default function MetricDailyCard() {
  /** Filters */
  const [sourceName, setSourceName] = useState("demo-source");
  const [metric, setMetric] = useState("events_total");
  const [start, setStart] = useState(() => isoDaysAgo(6));
  const [end, setEnd] = useState(() => isoDaysAgo(0));
  const [distinctField, setDistinctField] = useState("");

  /** Anomaly params */
  const [windowN, setWindowN] = useState(7); // days (rolling)
  const [zThresh, setZThresh] = useState(3); // z-score (rolling)
  const [algo, setAlgo] = useState<"rolling" | "iforest">("rolling");

  /** Data / UX */
  const [sources, setSources] = useState<Source[]>([]);
  const [metricOptions, setMetricOptions] = useState<string[]>([]);
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoLoaded, setAutoLoaded] = useState(false);

  /** Anomalies */
  const [showAnoms, setShowAnoms] = useState(false);
  const [anoms, setAnoms] = useState<AnomPoint[]>([]);
  const [showForecast, setShowForecast] = useState(false);
  const [forecast, setForecast] = useState<ForecastPoint[]>([]);

 /** Load sources once */
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API_BASE}/api/sources`);
        const js: any = await r.json();

        // Accept either a raw array or { data: [...] }
        const arr: any[] = Array.isArray(js) ? js : js?.data ?? [];

        // Normalize to [{id, name}]
        const data: Source[] = arr.map((s: any) =>
          typeof s === "string" ? { id: s, name: s } : { id: s.id ?? s.name, name: s.name ?? String(s) }
        );

        setSources(data);

        // Auto-select a source if none selected
        if (data.length && !data.find((s) => s.name === sourceName)) {
          setSourceName(data[0].name);
        }
      } catch (e: any) {
        console.error("Failed to load sources", e);
        setSources([]);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Load metric names whenever source changes */
  useEffect(() => {
    if (!sourceName) return;
    (async () => {
      try {
        const qs = new URLSearchParams({ source_name: String(sourceName) });
        const r = await fetch(`${API_BASE}/api/metrics/names?${qs.toString()}`);
        if (!r.ok) throw await jsonErr(r);
        const names: string[] = await r.json();
        setMetricOptions(names);
        if (names.length && !names.includes(metric)) setMetric(names[0]);
      } catch {
        setMetricOptions([]);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceName]);

  /** Auto-load once when we have a valid sourceName */
  useEffect(() => {
    if (autoLoaded) return;
    if (!sources.length) return;
    if (!sources.find((s) => s.name === sourceName)) return;
    setAutoLoaded(true);
    load(); // initial load
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sources, sourceName, autoLoaded]);

  /** Clear anomalies whenever filters change (prevents stale overlay). */
  useEffect(() => { setAnoms([]); setForecast([]); }, [sourceName, metric, start, end]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      if (start && end && start > end) throw new Error("Start date must be on or before End date.");
      if (!sourceName) throw new Error("Please select a source.");
      if (!metric) throw new Error("Please select a metric.");

      const qs = new URLSearchParams();
      qs.set("source_name", String(sourceName));
      qs.set("metric", String(metric));
      if (start) qs.set("start_date", start);
      if (end) qs.set("end_date", end);
      if (distinctField.trim()) qs.set("distinct_field", distinctField.trim());

      const resp = await fetch(`${API_BASE}/api/metrics/daily?${qs.toString()}`);
      if (!resp.ok) throw await jsonErr(resp);

      const json = await resp.json();
      const arr: Row[] = Array.isArray(json) ? json : json.items ?? json.data ?? [];
      arr.sort((a, b) => (getDate(a) || "").localeCompare(getDate(b) || ""));
      setRows(arr);

      // anomalies (if toggle is on)
      if (showAnoms && arr.length) {
        await fetchAnomalies(sourceName, metric, start, end, windowN, zThresh, algo, setAnoms, setError);
      } else {
        setAnoms([]);
      }

      // ✅ forecast (if toggle is on)
      if (showForecast && arr.length) {
        await fetchForecast(sourceName, metric, start, end, setForecast, setError);
      } else {
        setForecast([]);
      }

    } catch (e: any) {
      setRows([]);
      setAnoms([]);
      setForecast([]);
      setError(e?.message || "Failed to load data");
    } finally {
      setLoading(false);
    }
  }


  /** Re-fetch anomalies when toggled on (without requiring Apply) */
  useEffect(() => {
    (async () => {
      if (!showAnoms) return setAnoms([]);
      if (!rows.length) return;
      await fetchAnomalies(sourceName, metric, start, end, windowN, zThresh, algo, setAnoms, setError);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showAnoms]);

  /** Re-fetch forecast when toggled on (without requiring Apply) */
  useEffect(() => {
    (async () => {
      if (!showForecast) return setForecast([]);
      if (!rows.length) return;
      await fetchForecast(sourceName, metric, start, end, setForecast, setError);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showForecast]);


  /** Re-fetch anomalies when params change (if toggle is on and we have data) */
  useEffect(() => {
    (async () => {
      if (!showAnoms || !rows.length) return;
      await fetchAnomalies(sourceName, metric, start, end, windowN, zThresh, algo, setAnoms, setError);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [windowN, zThresh, algo]);

  /** Re-fetch forecast when filters change (if toggle is on and we have data) */
  useEffect(() => {
    (async () => {
      if (!showForecast || !rows.length) return;
      await fetchForecast(sourceName, metric, start, end, setForecast, setError);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceName, metric, start, end]);

  useEffect(() => {
    const arr = Array.isArray(sources) ? sources : [];
    if (!sourceName && arr.length > 0) {
      setSourceName(arr[0].name);
    }
  }, [sources, sourceName]);

  async function handleExportCSV() {
    if (!sourceName || !metric) return;
    setExporting(true);
    try {
      const qs = new URLSearchParams();
      qs.set("source_name", String(sourceName));
      qs.set("metric", String(metric));
      if (start) qs.set("start_date", start);
      if (end) qs.set("end_date", end);

      const resp = await fetch(`${API_BASE}/api/metrics/export/csv?${qs.toString()}`);
      if (!resp.ok) throw await jsonErr(resp);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `metric_daily_${metric}_${sourceName}_${start}_${end}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e?.message || "Export failed");
    } finally {
      setExporting(false);
    }
  }

  /** KPI aggregates for tiles */
  const kpis = useMemo(() => {
    let sum = 0, avg = 0, cnt = 0, dst = 0, n = 0;
    for (const r of rows) {
      const vSum = num(pick(r, "value_sum", "sum", "total", "value"));
      const vAvg = num(pick(r, "value_avg", "avg", "mean", "average"));
      const vCnt = num(pick(r, "value_count", "count", "rows", "n"));
      const vDst = num(pick(r, "value_distinct", "distinct", "unique"));
      sum += vSum; avg += vAvg; cnt += vCnt; dst += vDst; n++;
    }
    return {
      sum,
      avg: n ? +(avg / n).toFixed(2) : 0,
      count: cnt,
      distinct: dst || 0,
      hasDistinct: rows.some((r) => pick(r, "value_distinct", "distinct", "unique") != null),
    };
  }, [rows]);

// Prevent "sources.map is not a function" when data hasn't loaded yet
const safeSources = useMemo(
  () => (Array.isArray(sources) ? sources : []),
  [sources]
);

  /** UI */
  return (
    <div style={{ padding: 16, border: "1px solid #333", borderRadius: 12 }}>
      <h2 style={{ marginTop: 0 }}>Daily KPIs ({metric})</h2>
      {/* Filters row */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "end", marginBottom: 12 }}>
        <Labeled label="Source">
          <select
            value={sourceName || ""}
            onChange={(e) => setSourceName(e.target.value)}
            aria-label="Source"
          >
            {safeSources.length === 0 ? (
              <option value="" disabled>(no sources yet)</option>
            ) : (
              safeSources.map((s: any) => (
                <option key={s.id ?? s.name} value={s.name}>
                  {s.name}
                </option>
              ))
            )}
          </select>
        </Labeled>

        <Labeled label="Metric">
          {metricOptions.length ? (
            <select value={metric} onChange={(e) => setMetric(e.target.value)}>
              {metricOptions.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          ) : (
            <>
              <input list="metric-suggestions" value={metric} onChange={(e) => setMetric(e.target.value)} />
              <datalist id="metric-suggestions">
                {METRIC_SUGGESTIONS.map((m) => <option key={m} value={m} />)}
              </datalist>
            </>
          )}
        </Labeled>

        <Labeled label="Start">
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </Labeled>

        <Labeled label="End">
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        </Labeled>

        <Labeled label="Distinct Field (optional)" style={{ minWidth: 180 }}>
          <input placeholder="id / user_id …" value={distinctField} onChange={(e) => setDistinctField(e.target.value)} />
        </Labeled>

        {/* Anomaly Params */}
        <Labeled label="Anomaly window">
          <input
            type="number"
            min={3}
            max={60}
            value={windowN}
            onChange={(e) => setWindowN(Math.max(3, Math.min(60, Number(e.target.value) || 7)))}
          />
        </Labeled>

        <Labeled label="Z threshold">
          <input
            type="number"
            step="0.1"
            min={1}
            max={6}
            value={zThresh}
            onChange={(e) => setZThresh(Math.max(1, Math.min(6, Number(e.target.value) || 3)))}
            disabled={algo === "iforest"}
          />
        </Labeled>

        <Labeled label="Algorithm">
          <select value={algo} onChange={(e) => setAlgo(e.target.value as "rolling" | "iforest")}>
            <option value="rolling">Rolling Z-score</option>
            <option value="iforest">Isolation Forest</option>
          </select>
        </Labeled>

        <button onClick={load} disabled={loading} style={{ padding: "8px 12px" }}>
          {loading ? "Loading…" : "Apply"}
        </button>

        <button
          onClick={() => {
            setMetric(metricOptions[0] ?? "events_total");
            setStart(isoDaysAgo(6));
            setEnd(isoDaysAgo(0));
            setDistinctField("");
            setWindowN(7);
            setZThresh(3);
            setAlgo("rolling");
            setError(null);
            setAnoms([]);
          }}
          disabled={loading}
          style={{ padding: "8px 12px", opacity: 0.9 }}
        >
          Reset
        </button>

        <button onClick={handleExportCSV} disabled={loading || exporting || !metric || !sourceName} style={{ padding: "8px 12px" }}>
          {exporting ? "Exporting…" : "Export CSV"}
        </button>

        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            aria-label="Show anomalies"
            data-testid="toggle-anomalies"
            checked={showAnoms}
            onChange={(e) => {
              setShowAnoms(e.target.checked);
              if (e.target.checked && rows.length) {
                fetchAnomalies(sourceName, metric, start, end, windowN, zThresh, algo, setAnoms, setError);
              } else {
                setAnoms([]);
              }
            }}
            disabled={loading || rows.length === 0}
          />
          Show anomalies
        </label>

        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            aria-label="Show forecast"
            data-testid="toggle-forecast"
            checked={showForecast}
            onChange={(e) => setShowForecast(e.target.checked)}
            disabled={loading || rows.length === 0}
          />
          Show forecast
        </label>

      </div>

      {/* Error banner */}
      {error && (
        <div style={{ color: "#f87171", marginBottom: 8 }} aria-live="polite">
          ⚠️ {error}
        </div>
      )}

      {/* KPI tiles */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
        <Tile title="Sum" value={fmtNum(kpis.sum)} />
        <Tile title="Average" value={fmtNum(kpis.avg)} />
        <Tile title="Count" value={fmtNum(kpis.count)} />
        <Tile title="Distinct" value={kpis.hasDistinct ? fmtNum(kpis.distinct) : "—"} />
      </div>

      {/* Table */}
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            {["Date", "Source", "Metric", "Sum", "Avg", "Count", "Distinct"].map((h) => (
              <th key={h} style={thTd(true)}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const date = getDate(r);
            const src = pick(r, "source_id", "source");
            const met = pick(r, "metric", "name");
            const vSum = pick(r, "value_sum", "sum", "total", "value");
            const vAvg = pick(r, "value_avg", "avg", "mean", "average");
            const vCnt = pick(r, "value_count", "count", "rows", "n");
            const vDst = pick(r, "value_distinct", "distinct", "unique");
            return (
              <tr key={`${date}-${i}`}>
                <td style={thTd()}>{fmt(date)}</td>
                <td style={thTd()}>{fmt(src)}</td>
                <td style={thTd()}>{fmt(met)}</td>
                <td style={thTd()}>{fmt(vSum)}</td>
                <td style={thTd()}>{fmt(vAvg)}</td>
                <td style={thTd()}>{fmt(vCnt)}</td>
                <td style={thTd()}>{fmt(vDst)}</td>
              </tr>
            );
          })}
          {rows.length === 0 && !loading && (
            <tr>
              <td style={thTd()} colSpan={7}>
                No data for this selection. Try a wider date range or different filters.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {/* Chart */}
      {rows.length > 0 && (
        <div style={{ marginTop: 12 }} aria-busy={loading}>
          <MetricDailyChart
            key={`${sourceName}-${metric}-${showAnoms ? "A" : "N"}`}
            rows={rows.map((r) => ({
              date: getDate(r) || "",
              value: num(pick(r, "value_sum", "sum", "total", "value")),
            }))}
            anomalies={anoms}
            forecast={forecast}
          />
        </div>
      )}
    </div>
  );
}

/* ---------- helpers ---------- */
function pick<T extends object, K extends keyof any>(o: T, ...ks: K[]) {
  for (const k of ks) {
    const v = (o as any)[k];
    if (v !== undefined && v !== null) return v;
  }
  return undefined;
}
function getDate(r: Row) {
  return (pick(r, "metric_date", "date", "day") as string | undefined) ?? undefined;
}
function fmt(v: any) {
  return v === undefined || v === null || v === "" ? "—" : String(v);
}
function num(v: any) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}
function fmtNum(v: number) {
  return Number.isFinite(v) ? v.toString() : "—";
}
function isoDaysAgo(n: number) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}
async function jsonErr(r: Response) {
  try {
    const j = await r.json();
    return new Error(String(j?.detail || j?.title || `HTTP ${r.status}`));
  } catch {
    return new Error(`HTTP ${r.status}`);
  }
}
function thTd(header = false): React.CSSProperties {
  return {
    border: "1px solid #2a2a2a",
    padding: "8px 10px",
    textAlign: "left",
    background: header ? "#111" : "transparent",
  };
}
function Tile({ title, value }: { title: string; value: string | number }) {
  return (
    <div style={{ border: "1px solid #2a2a2a", borderRadius: 12, padding: "12px 14px", minWidth: 160 }}>
      <div style={{ fontSize: 12, color: "#9ca3af" }}>{title}</div>
      <div style={{ fontSize: 20, fontWeight: 600, marginTop: 4 }}>{value}</div>
    </div>
  );
}
function Labeled(props: React.PropsWithChildren<{ label: string; style?: React.CSSProperties }>) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, ...props.style }}>
      <label style={{ fontSize: 12, color: "#9ca3af" }}>{props.label}</label>
      {props.children}
    </div>
  );
}

/** Param-aware anomaly fetch (rolling z-score / isolation forest) */
async function fetchAnomalies(
  sourceName: string,
  metric: string,
  start: string | undefined,
  end: string | undefined,
  windowN: number,
  zThresh: number,
  algo: "rolling" | "iforest",
  setAnoms: (v: AnomPoint[]) => void,
  setError: (v: string | null) => void
) {
  try {
    const qs = new URLSearchParams({
      source_name: String(sourceName),
      metric: String(metric),
    });
    if (start) qs.set("start_date", start);
    if (end) qs.set("end_date", end);

    let url: string;
    if (algo === "rolling") {
      qs.set("window", String(windowN));
      qs.set("z_thresh", String(zThresh));
      url = `${API_BASE}/api/metrics/anomaly/rolling?${qs.toString()}`;
    } else {
      // try a slightly higher contamination so a tiny dataset can flag outliers
      qs.set("contamination", "0.15");
      url = `${API_BASE}/api/metrics/anomaly/iforest?${qs.toString()}`;
    }

    const r = await fetch(url);
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    const js: any = await r.json();

    // ---- robust array extraction (handles {data:{points:[...]}} etc) ----
    const raw: any[] =
      Array.isArray(js) ? js :
      Array.isArray(js?.data) ? js.data :
      Array.isArray(js?.points) ? js.points :
      Array.isArray(js?.data?.points) ? js.data.points :
      Array.isArray(js?.results) ? js.results :
      [];

    // normalize to your chart shape and filter
    const normalized: AnomPoint[] = raw
      .map((row: any) => {
        const z =
          typeof row.z === "number"
            ? row.z
            : typeof row.score === "number"
            ? row.score
            : undefined;

        const flagged =
          row.is_outlier === true ||
          row.is_anomaly === true ||
          row.outlier === true ||
          row.anomaly === true;

        return {
          date: String(row.metric_date ?? row.date ?? row.ts ?? ""),
          value: Number(row.value ?? row.value_sum ?? row.y ?? row.count ?? 0),
          z,
          flagged,
        };
      })
      // plot explicitly-flagged, OR anything exceeding current z threshold
      .filter((r) => r.date && (r.flagged || (typeof r.z === "number" && Math.abs(r.z) >= zThresh)))
      .map(({ date, value, z }) => ({ date, value, z }));

    setAnoms(normalized);
  } catch (e: any) {
    console.error("fetchAnomalies failed:", e);
    setAnoms([]);
    setError(e?.message || "Failed to load anomalies");
  }
}

async function fetchForecast(
  sourceName: string,
  metric: string,
  start: string | undefined,
  end: string | undefined,
  setForecast: (v: ForecastPoint[]) => void,
  setError: (v: string | null) => void
) {
  try {
    const key = `fc:${sourceName}:${metric}:${start}:${end}`;
    if (FC_CACHE.has(key)) { setForecast(FC_CACHE.get(key)!); return; }

    const qs = new URLSearchParams();
    qs.set("source_name", String(sourceName));
    qs.set("metric", String(metric));
    if (start) qs.set("start_date", start);
    if (end) qs.set("end_date", end);

    const r = await fetch(`${API_BASE}/api/forecast/daily?${qs.toString()}`);
    if (!r.ok) throw await jsonErr(r);
    const js: any = await r.json();

    // Accept [], {data:[]}, {points:[]}, or {data:{points:[]}}
    const raw: any[] =
      Array.isArray(js) ? js :
      Array.isArray(js?.data) ? js.data :
      Array.isArray(js?.points) ? js.points :
      Array.isArray(js?.data?.points) ? js.data.points :
      [];

    const mapped: ForecastPoint[] = raw
      .map((row: any) => ({
        date: String(row.metric_date ?? row.date ?? row.ts ?? ""),
        yhat: Number(row.yhat ?? row.y_pred ?? row.prediction ?? row.value ?? row.y ?? 0),
      }))
      .filter(p => p.date && Number.isFinite(p.yhat));

    FC_CACHE.set(key, mapped);
    setForecast(mapped);
  } catch (e: any) {
    setForecast([]);
    setError(e?.message || "Failed to load forecast");
  }
}
