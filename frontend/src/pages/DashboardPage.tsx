// frontend/src/pages/DashboardPage.tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { DashboardShell } from "../components/dashboard/DashboardShell";
import { FiltersBar } from "../components/dashboard/FiltersBar";
import { KpiTiles } from "../components/dashboard/KpiTiles";
import MetricDailyChart from "../components/MetricDailyChart";
import MetricDailyTableView from "../components/dashboard/MetricDailyTableView";
import { Text } from "../ui";

/* ---------- config ---------- */
const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

/* ---------- types ---------- */
type Row = {
  metric_date?: string; date?: string; day?: string;
  source_id?: number | string; source?: string;
  metric?: string; name?: string;
  value_sum?: number; sum?: number; total?: number; value?: number;
  value_avg?: number; avg?: number; mean?: number; average?: number;
  value_count?: number; count?: number; rows?: number; n?: number;
  value_distinct?: number; distinct?: number; unique?: number;
};
type AnomPoint = { date: string; value: number; z?: number };
type ForecastPoint = { date: string; yhat: number };

/* ---------- helpers ---------- */
function isoDaysAgo(n: number) { const d=new Date(); d.setDate(d.getDate()-n); return d.toISOString().slice(0,10); }
function pick<T extends object, K extends keyof any>(o: T, ...ks: K[]) { for (const k of ks) { const v=(o as any)[k]; if (v!=null) return v; } }
function getDate(r: Row) { return (pick(r,"metric_date","date","day") as string | undefined) ?? undefined; }
function num(v: any) { const n=Number(v); return Number.isFinite(n)?n:0; }

/* ---------- overlays: anomalies & forecast ---------- */
async function fetchAnomalies(params: {
  sourceName: string; metric: string; start?: string; end?: string;
  windowN?: number; zThresh?: number; signal?: AbortSignal;
}): Promise<AnomPoint[]> {
  const { sourceName, metric, start, end, windowN = 7, zThresh = 3, signal } = params;
  const qs = new URLSearchParams({ source_name: String(sourceName), metric: String(metric) });
  if (start) qs.set("start_date", start);
  if (end) qs.set("end_date", end);
  qs.set("window", String(windowN));
  qs.set("z_thresh", String(zThresh));

  const r = await fetch(`${API_BASE}/api/metrics/anomaly/rolling?${qs.toString()}`, { signal });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const js: any = await r.json();

  let raw: any = null;
  if (Array.isArray(js)) raw = js;
  else if (Array.isArray(js?.data)) raw = js.data;
  else if (Array.isArray(js?.points)) raw = js.points;
  else if (Array.isArray(js?.results)) raw = js.results;
  else if (Array.isArray(js?.anomalies)) raw = js.anomalies;
  else if (Array.isArray(js?.data?.points)) raw = js.data.points;
  else if (Array.isArray(js?.dates) && Array.isArray(js?.values)) {
    const dates = js.dates, values = js.values, zArr = Array.isArray(js?.z) ? js.z : [];
    raw = dates.map((d: any, i: number) => ({ date: d, value: values[i], z: zArr[i] }));
  } else if (js && typeof js === "object") {
    const maybe = Object.entries(js)
      .filter(([k, v]) => typeof v === "object" && (/[0-9]{4}-[0-9]{2}-[0-9]{2}/.test(k) || "metric_date" in (v as any) || "date" in (v as any)))
      .map(([k, v]: any) => ({ date: v.metric_date ?? v.date ?? k, value: v.value ?? v.value_sum ?? v.y ?? v.count ?? 0, z: v.z ?? v.score, flagged: v.is_anomaly ?? v.is_outlier ?? v.anomaly ?? v.outlier ?? v.flagged }));
    if (maybe.length) raw = maybe;
  }
  if (!Array.isArray(raw)) return [];

  const pts: AnomPoint[] = raw
    .map((row: any) => {
      const date = String(row.metric_date ?? row.date ?? row.ts ?? "");
      const value = Number(row.value ?? row.value_sum ?? row.y ?? row.count ?? 0);
      const flagged =
        row.is_outlier === true || row.is_anomaly === true ||
        row.outlier === true    || row.anomaly === true    ||
        row.flagged === true;
      const z = typeof row.z === "number" ? row.z : (typeof row.score === "number" ? row.score : undefined);
      return { date, value, z, flagged } as any;
    })
    .filter((p: any) => {
      if (!p.date || !Number.isFinite(p.value)) return false;
      if (p.flagged === true) return true;
      if (typeof p.z === "number") return Math.abs(p.z) >= (zThresh ?? 3);
      return false;
    })
    .map(({ date, value, z }) => ({ date, value, z }));
  return pts;
}

const FC_CACHE = new Map<string, ForecastPoint[]>();
async function fetchForecast(sourceName: string, metric: string, start?: string, end?: string, signal?: AbortSignal): Promise<ForecastPoint[]> {
  const key = `fc:${sourceName}:${metric}:${start}:${end}`;
  if (FC_CACHE.has(key)) return FC_CACHE.get(key)!;

  const qs = new URLSearchParams({ source_name: String(sourceName), metric: String(metric) });
  if (start) qs.set("start_date", start);
  if (end) qs.set("end_date", end);
  const r = await fetch(`${API_BASE}/api/forecast/daily?${qs.toString()}`, { signal });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);

  const js: any = await r.json();
  const raw: any[] = Array.isArray(js) ? js : js.data ?? js.points ?? js?.data?.points ?? [];
  const fc = raw
    .map((row: any) => ({
      date: String(row.metric_date ?? row.date ?? row.ts ?? ""),
      yhat: Number(row.yhat ?? row.y_pred ?? row.prediction ?? row.value ?? row.y ?? 0),
    }))
    .filter(p => p.date && Number.isFinite(p.yhat));
  FC_CACHE.set(key, fc);
  return fc;
}

/* ---------- page ---------- */
export default function DashboardPage() {
  // Filters
  const [sourceName, setSourceName] = useState("demo-source");
  const [metric, setMetric] = useState("events_total");
  const [start, setStart] = useState(() => isoDaysAgo(6));
  const [end, setEnd] = useState(() => isoDaysAgo(0));
  const [dateRange, setDateRange] = useState<"7"|"14"|"30">("7");

  // Toggles + anomaly params
  const [showAnoms, setShowAnoms] = useState(false);
  const [showForecast, setShowForecast] = useState(false);
  const [windowN, setWindowN] = useState(7);
  const [zThresh, setZThresh] = useState(3);

  // Data
  const [rows, setRows] = useState<Row[]>([]);
  const [anoms, setAnoms] = useState<AnomPoint[]>([]);
  const [forecast, setForecast] = useState<ForecastPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* ---------- upload state ---------- */
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);

  // Quick range fills fields; still editable
  useEffect(() => {
    const n = Number(dateRange);
    setStart(isoDaysAgo(n - 1));
    setEnd(isoDaysAgo(0));
  }, [dateRange]);

  // KPIs
  const kpis = useMemo(() => {
    let sum=0, avg=0, cnt=0, dst=0, n=0;
    for (const r of rows) {
      sum += num(pick(r,"value_sum","sum","total","value"));
      avg += num(pick(r,"value_avg","avg","mean","average"));
      cnt += num(pick(r,"value_count","count","rows","n"));
      dst += num(pick(r,"value_distinct","distinct","unique"));
      n++;
    }
    return {
      sum,
      avg: n ? +(avg/n).toFixed(2) : 0,
      count: cnt,
      distinct: dst || 0,
      hasDistinct: rows.some(r => pick(r,"value_distinct","distinct","unique")!=null),
    };
  }, [rows]);

  /* ---------- effect-driven base fetch ---------- */
  const query = useMemo(() => ({
    sourceName, metric, start, end
  }), [sourceName, metric, start, end]);

  useEffect(() => {
    // Clear UI immediately to avoid stale series/rows
    setRows([]);
    setAnoms([]);
    setForecast([]);
    setError(null);

    const ctrl = new AbortController();
    const load = async () => {
      try {
        if (start && end && start > end) throw new Error("Start must be on/before End.");
        setLoading(true);

        const qs = new URLSearchParams({ source_name: String(sourceName), metric: String(metric) });
        if (start) qs.set("start_date", start);
        if (end) qs.set("end_date", end);

        const r = await fetch(`${API_BASE}/api/metrics/daily?${qs.toString()}`, { signal: ctrl.signal });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const js = await r.json();
        const arr: Row[] = Array.isArray(js) ? js : js.items ?? js.data ?? [];
        arr.sort((a,b)=>(getDate(a)||"").localeCompare(getDate(b)||""));
        setRows(arr);
      } catch (e:any) {
        if (e?.name !== "AbortError") {
          setError(e?.message || "Failed to load data");
        }
      } finally {
        setLoading(false);
      }
    };
    void load();

    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(query)]);

  /* ---------- overlays fetch when rows/toggles change ---------- */
  useEffect(() => {
    const ctrl = new AbortController();

    const loadOverlays = async () => {
      if (!rows.length) { setAnoms([]); setForecast([]); return; }
      try {
        if (showAnoms) {
          const pts = await fetchAnomalies({
            sourceName, metric, start, end, windowN, zThresh, signal: ctrl.signal
          });
          setAnoms(pts);
        } else setAnoms([]);

        if (showForecast) {
          const fc = await fetchForecast(sourceName, metric, start, end, ctrl.signal);
          setForecast(fc);
        } else setForecast([]);
      } catch (e:any) {
        if (e?.name !== "AbortError") setError(e?.message || "Overlay fetch failed");
      }
    };

    void loadOverlays();
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows.length, showAnoms, showForecast, windowN, zThresh, sourceName, metric, start, end]);

  /* ---------- Upload handler (calls /api/ingest) ---------- */
  async function handleUpload(file: File | null) {
    if (!file) return;
    setUploading(true);
    setUploadMsg(null);
    try {
      const ct = (file.type || "").toLowerCase();
      if (!ct.includes("csv")) {
        setUploading(false);
        setUploadMsg("Only CSV is supported from the button for now.");
        return;
      }
      const qs = new URLSearchParams({
        source_name: String(sourceName || "demo-source"),
        default_metric: String(metric || "events_total"),
      });
      const form = new FormData();
      form.append("file", file, file.name);
      const resp = await fetch(`${API_BASE}/api/ingest?${qs.toString()}`, {
        method: "POST",
        body: form,
      });
      const body = await resp.json().catch(() => ({}));
      if (!resp.ok || body?.ok === false) {
        throw new Error(body?.error?.message || `Upload failed (HTTP ${resp.status})`);
      }
      setUploadMsg(`Ingested ${body?.data?.rows_ingested ?? "?"} rows (${file.name}).`);
      // After ingest, rows will refresh automatically because query didn't change,
      // so explicitly nudge by toggling dateRange to itself (noop), or call a quick refresh:
      setEnd((e) => e); // no-op that keeps state but re-triggers base effect only if you prefer to change
    } catch (e: any) {
      setUploadMsg(e?.message || "Upload failed.");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  /* ---------- Reset handler (pure state; effect does the fetch) ---------- */
  function handleReset() {
    const newStart = isoDaysAgo(6);
    const newEnd   = isoDaysAgo(0);

    // Set defaults. The base effect above will clear data and fetch once.
    setSourceName("demo-source");
    setMetric("events_total");
    setDateRange("7"); // will also update start/end via its effect
    setStart(newStart);
    setEnd(newEnd);

    setShowAnoms(false);
    setShowForecast(false);
    setWindowN(7);
    setZThresh(3);
  }

  /* ---------- chart remount key to avoid stale series ---------- */
  const chartKey = useMemo(
    () => `${sourceName}|${metric}|${start}|${end}|${showAnoms}|${showForecast}`,
    [sourceName, metric, start, end, showAnoms, showForecast]
  );

  // Filters UI
  const filters = (
    <FiltersBar
      Source={
        <select data-testid="filter-source" value={sourceName} onChange={e=>setSourceName(e.target.value)}>
          <option value="demo-source">demo-source</option>
        </select>
      }
      Metric={
        <select data-testid="filter-metric" value={metric} onChange={e=>setMetric(e.target.value)}>
          <option value="events_total">events_total</option>
        </select>
      }
      Start={
        <input data-testid="filter-start" type="date" value={start}
               onChange={(e)=>setStart(e.target.value)} max={end || undefined} />
      }
      End={
        <input data-testid="filter-end" type="date" value={end}
               onChange={(e)=>setEnd(e.target.value)} min={start || undefined} />
      }
      Apply={
        <button data-testid="btn-run" className="sd-btn" onClick={() => {
          // manual re-run: touch end to re-trigger effect without changing values
          setEnd((e) => e);
        }} disabled={loading}>
          {loading ? "Running…" : "Run"}
        </button>
      }
      Reset={
        <button data-testid="btn-reset" className="sd-btn ghost" disabled={loading} onClick={handleReset}>
          Reset
        </button>
      }
      Extra={
        <div className="sd-stack row" style={{ gap: 10, alignItems: "center" }}>
          <select data-testid="quick-range" value={dateRange}
                  onChange={(e)=>setDateRange(e.target.value as any)}>
            <option value="7">Last 7 days</option>
            <option value="14">Last 14 days</option>
            <option value="30">Last 30 days</option>
          </select>

          <label className="small sd-muted">Window</label>
          <input data-testid="anoms-window" type="number" min={3} max={60} value={windowN}
                 onChange={(e)=>setWindowN(Math.max(3, Math.min(60, Number(e.target.value)||7)))}
                 style={{ width: 64 }} />

          <label className="small sd-muted">z≥</label>
          <input data-testid="anoms-z" type="number" step="0.1" min={0} max={6} value={zThresh}
                 onChange={(e)=>setZThresh(Math.max(0, Math.min(6, Number(e.target.value)||3)))}
                 style={{ width: 64 }} />

          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input data-testid="toggle-anoms" type="checkbox"
                   checked={showAnoms} onChange={(e)=>setShowAnoms(e.target.checked)} />
            Show anomalies
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input data-testid="toggle-forecast" type="checkbox"
                   checked={showForecast} onChange={(e)=>setShowForecast(e.target.checked)} />
            Show forecast
          </label>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,text/csv"
            style={{ display: "none" }}
            onChange={(e)=>handleUpload(e.target.files?.[0] ?? null)}
            data-testid="upload-file"
          />
          <button
            type="button"
            className="sd-btn"
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? "Uploading…" : "Upload CSV"}
          </button>
          {uploadMsg && <span className="sd-text-xs sd-muted" aria-live="polite">{uploadMsg}</span>}
        </div>
      }
    />
  );

  return (
    <DashboardShell
      headerRight={null}
      filters={filters}
      tiles={<KpiTiles kpis={kpis} />}
      left={
        <div>
          <Text variant="h3">Daily KPIs ({metric})</Text>
          {error && <Text variant="small" className="sd-my-2" muted>⚠️ {error}</Text>}
          {rows.length === 0
            ? <Text className="sd-my-2" muted>No data for this selection. Try a wider range.</Text>
            : <div className="sd-my-2">
                <MetricDailyChart
                  key={chartKey}
                  rows={rows.map(r=>({ date: getDate(r)||"", value: num(pick(r,"value_sum","sum","total","value")) }))}
                  anomalies={anoms}
                  forecast={forecast}
                />
                {/* hidden lists for test hooks */}
                <ul data-testid="anomaly-list" style={{ display: "none" }}>
                  {anoms.map((a, i) => (
                    <li key={i} data-date={a.date} data-value={a.value} data-z={a.z ?? ""} />
                  ))}
                </ul>
                <ul data-testid="forecast-list" style={{ display: "none" }}>
                  {forecast.map((p, i) => (
                    <li key={i} data-date={p.date} data-yhat={p.yhat} />
                  ))}
                </ul>
              </div>}
        </div>
      }
      right={<MetricDailyTableView rows={rows} />}
    />
  );
}
