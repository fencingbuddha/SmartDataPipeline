// frontend/src/pages/DashboardPage.tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { toPng } from "html-to-image";
import { saveAs } from "file-saver";
import { DashboardShell } from "../components/dashboard/DashboardShell";
import { FiltersBar } from "../components/dashboard/FiltersBar";
import { KpiTiles } from "../components/dashboard/KpiTiles";
import MetricDailyChart from "../components/MetricDailyChart";
import MetricDailyTableView from "../components/dashboard/MetricDailyTableView";
import { Text } from "../ui";
import { ReliabilityBadge, DetailsDrawer, useReliability } from "../ui";
import {
  authApi,
  buildUrl,
  getJson,
  postJson,
  request,
  tokenStore,
} from "../lib/api";

/* ---------- types ---------- */
type Row = {
  metric_date?: string;
  date?: string;
  day?: string;
  source_id?: number | string;
  source?: string;
  metric?: string;
  name?: string;
  value_sum?: number;
  sum?: number;
  total?: number;
  value?: number;
  value_avg?: number;
  avg?: number;
  mean?: number;
  average?: number;
  value_count?: number;
  count?: number;
  rows?: number;
  n?: number;
  value_distinct?: number;
  distinct?: number;
  unique?: number;
};
type AnomPoint = { date: string; value: number; z?: number };
type ForecastPoint = { date: string; yhat: number };
type Source = { id: number | string; name: string };

function withAuthHeaders(
  headers: Record<string, string> = {},
): Record<string, string> {
  const next: Record<string, string> = { ...headers };
  if (tokenStore.access) {
    next.Authorization = `Bearer ${tokenStore.access}`;
  }
  return next;
}

/* ---------- helpers ---------- */
function isoDaysAgo(n: number) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}
function pick<T extends object, K extends keyof any>(o: T, ...ks: K[]) {
  for (const k of ks) {
    const v = (o as any)[k];
    if (v != null) return v;
  }
}
function getDate(r: Row) {
  return (
    (pick(r, "metric_date", "date", "day") as string | undefined) ?? undefined
  );
}
function num(v: any) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

/* ---------- overlays: anomalies & forecast ---------- */
async function fetchAnomalies(params: {
  sourceName: string;
  metric: string;
  start?: string;
  end?: string;
  windowN?: number;
  zThresh?: number;
  signal?: AbortSignal;
}): Promise<AnomPoint[]> {
  const {
    sourceName,
    metric,
    start,
    end,
    windowN = 7,
    zThresh = 3,
    signal,
  } = params;
  const js: any = await getJson(
    "/api/metrics/anomaly/rolling",
    {
      source_name: String(sourceName),
      metric: String(metric),
      start_date: start,
      end_date: end,
      window: windowN,
      z_thresh: zThresh,
    },
    signal,
  );

  let raw: any = null;
  if (Array.isArray(js)) raw = js;
  else if (Array.isArray(js?.data)) raw = js.data;
  else if (Array.isArray(js?.points)) raw = js.points;
  else if (Array.isArray(js?.results)) raw = js.results;
  else if (Array.isArray(js?.anomalies)) raw = js.anomalies;
  else if (Array.isArray(js?.data?.points)) raw = js.data.points;
  else if (Array.isArray(js?.dates) && Array.isArray(js?.values)) {
    const dates = js.dates,
      values = js.values,
      zArr = Array.isArray(js?.z) ? js.z : [];
    raw = dates.map((d: any, i: number) => ({
      date: d,
      value: values[i],
      z: zArr[i],
    }));
  } else if (js && typeof js === "object") {
    const maybe = Object.entries(js)
      .filter(
        ([k, v]) =>
          typeof v === "object" &&
          (/[0-9]{4}-[0-9]{2}-[0-9]{2}/.test(k) ||
            "metric_date" in (v as any) ||
            "date" in (v as any)),
      )
      .map(([k, v]: any) => ({
        date: v.metric_date ?? v.date ?? k,
        value: v.value ?? v.value_sum ?? v.y ?? v.count ?? 0,
        z: v.z ?? v.score,
        flagged:
          v.is_anomaly ?? v.is_outlier ?? v.anomaly ?? v.outlier ?? v.flagged,
      }));
    if (maybe.length) raw = maybe;
  }
  if (!Array.isArray(raw)) return [];

  const pts: AnomPoint[] = raw
    .map((row: any) => {
      const date = String(row.metric_date ?? row.date ?? row.ts ?? "");
      const value = Number(
        row.value ?? row.value_sum ?? row.y ?? row.count ?? 0,
      );
      const flagged =
        row.is_outlier === true ||
        row.is_anomaly === true ||
        row.outlier === true ||
        row.anomaly === true ||
        row.flagged === true;
      const z =
        typeof row.z === "number"
          ? row.z
          : typeof row.score === "number"
            ? row.score
            : undefined;
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
async function fetchForecast(
  sourceName: string,
  metric: string,
  start?: string,
  end?: string,
  signal?: AbortSignal,
  horizon?: number,
  nonce?: number,
): Promise<ForecastPoint[]> {
  const key = `fc:${sourceName}:${metric}:${start}:${end}:${horizon ?? "n"}:${nonce ?? 0}`;
  if (FC_CACHE.has(key)) return FC_CACHE.get(key)!;

  const params: Record<string, string | number | undefined> = {
    source_name: String(sourceName),
    metric: String(metric),
  };
  if (horizon && horizon > 0) {
    params.horizon = Math.min(30, Math.max(1, horizon));
  } else {
    if (start) params.start_date = start;
    if (end) params.end_date = end;
  }
  if (nonce) params.nocache = nonce;

  const js: any = await getJson("/api/forecast/daily", params, signal);
  const raw: any[] = Array.isArray(js)
    ? js
    : (js.data ?? js.points ?? js?.data?.points ?? []);

  const fc: ForecastPoint[] = raw
    .map((row: any) => ({
      date: String(
        row.forecast_date ??
          row.target_date ??
          row.metric_date ??
          row.date ??
          row.ts ??
          "",
      ),
      yhat: Number(
        row.yhat ?? row.y_pred ?? row.prediction ?? row.value ?? row.y ?? NaN,
      ),
    }))
    .filter((p) => p.date && Number.isFinite(p.yhat));

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
  const [dateRange, setDateRange] = useState<"7" | "14" | "30">("7");

  // Reliability UI state
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Forecast reliability data for the current Source/Metric
  const { data: rel, loading: relLoading, error: relError } = useReliability({
    sourceName,
    metric,
  });

  // Sources / metric names (dynamic)
  const [sources, setSources] = useState<Source[]>([]);
  const sourceNamesKey = sources.map((s) => s.name).join(",");
  const [metricOptions, setMetricOptions] = useState<string[]>([]);

  // Toggles + anomaly params
  const [showAnoms, setShowAnoms] = useState(false);
  const [showForecast, setShowForecast] = useState(false);
  const [windowN, setWindowN] = useState(7);
  const [zThresh, setZThresh] = useState(3);

  // Data
  const [rows, setRows] = useState<Row[]>([]);
  const [anoms, setAnoms] = useState<AnomPoint[]>([]);
  const [forecast, setForecast] = useState<ForecastPoint[]>([]);
  const [fcTick, setFcTick] = useState(0); // nonce to force one refetch when toggled ON
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Clear forecast cache on filter changes so a subsequent toggle ON refetches
  useEffect(() => {
    FC_CACHE.clear();
  }, [sourceName, metric, start, end]);

  /* ---------- upload state ---------- */
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);

  const exportRef = useRef<HTMLDivElement | null>(null);

  /* ---------- load sources + metric names ---------- */
  async function loadSources() {
    const js: any = await getJson("/api/sources");
    const arr: any[] = Array.isArray(js)
      ? js
      : Array.isArray(js?.data)
        ? js.data
        : [];
    const data: Source[] = arr.map((s: any) =>
      typeof s === "string"
        ? { id: s, name: s }
        : { id: s.id ?? s.name, name: s.name ?? String(s) },
    );
    setSources(data);
    if (data.length && !data.find((s) => s.name === sourceName)) {
      setSourceName(data[0].name);
    }
    console.log(
      "loadSources →",
      data.map((s) => s.name),
    );
  }
  useEffect(() => {
    void loadSources();
  }, []);

  async function loadMetricNames(sn: string) {
    if (!sn) {
      setMetricOptions([]);
      return;
    }
    try {
      const names = await getJson<string[]>("/api/metrics/names", {
        source_name: String(sn),
      });
      setMetricOptions(names || []);
      if (names?.length && !names.includes(metric)) setMetric(names[0]);
      console.log("metric names for", sn, "→", names);
    } catch {
      setMetricOptions([]);
    }
  }
  useEffect(() => {
    void loadMetricNames(sourceName);
  }, [sourceName]);

  // Quick range fills fields; still editable
  useEffect(() => {
    const n = Number(dateRange);
    setStart(isoDaysAgo(n - 1));
    setEnd(isoDaysAgo(0));
  }, [dateRange]);

  // KPIs
  const kpis = useMemo(() => {
    let sum = 0,
      avg = 0,
      cnt = 0,
      dst = 0,
      n = 0;
    for (const r of rows) {
      sum += num(pick(r, "value_sum", "sum", "total", "value"));
      avg += num(pick(r, "value_avg", "avg", "mean", "average"));
      cnt += num(pick(r, "value_count", "count", "rows", "n"));
      dst += num(pick(r, "value_distinct", "distinct", "unique"));
      n++;
    }
    return {
      sum,
      avg: n ? +(avg / n).toFixed(2) : 0,
      count: cnt,
      distinct: dst || 0,
      hasDistinct: rows.some(
        (r) => pick(r, "value_distinct", "distinct", "unique") != null,
      ),
    };
  }, [rows]);

  /* ---------- effect-driven base fetch ---------- */
  const query = useMemo(
    () => ({
      sourceName,
      metric,
      start,
      end,
    }),
    [sourceName, metric, start, end],
  );

  useEffect(() => {
    // Clear UI immediately to avoid stale series/rows
    setRows([]);
    setAnoms([]);
    setForecast([]);
    setError(null);

    const ctrl = new AbortController();
    const load = async () => {
      try {
        if (start && end && start > end)
          throw new Error("Start must be on/before End.");
        setLoading(true);

        const params: Record<string, string> = {
          source_name: String(sourceName),
          metric: String(metric),
        };
        if (start) params.start_date = start;
        if (end) params.end_date = end;

        const js = await getJson<any>(
          "/api/metrics/daily",
          params,
          ctrl.signal,
        );
        const arr: Row[] = Array.isArray(js) ? js : (js.items ?? js.data ?? []);
        arr.sort((a, b) => (getDate(a) || "").localeCompare(getDate(b) || ""));
        setRows(arr);
      } catch (e: any) {
        if (e?.name !== "AbortError")
          setError(e?.message || "Failed to load data");
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
      if (!rows.length) {
        setAnoms([]);
        setForecast([]);
        return;
      }
      try {
        if (showAnoms) {
          const pts = await fetchAnomalies({
            sourceName,
            metric,
            start,
            end,
            windowN,
            zThresh,
            signal: ctrl.signal,
          });
          setAnoms(pts);
        } else setAnoms([]);

        if (showForecast) {
          const H = 7;
          const fc = await fetchForecast(
            sourceName,
            metric,
            undefined,
            undefined,
            ctrl.signal,
            H,
            fcTick,
          );
          setForecast(fc);
        } else {
          setForecast([]);
        }
      } catch (e: any) {
        if (e?.name !== "AbortError")
          setError(e?.message || "Overlay fetch failed");
      }
    };

    void loadOverlays();
    return () => ctrl.abort();
     
  }, [
    rows.length,
    showAnoms,
    showForecast,
    windowN,
    zThresh,
    sourceName,
    metric,
    start,
    end,
    fcTick,
  ]);

  /* ---------- Upload handler (calls /api/ingest) ---------- */
  async function handleUpload(file: File | null) {
    if (!file) return;
    setUploading(true);
    setUploadMsg(null);
    try {
      const isJson =
        file.type?.toLowerCase().includes("json") ||
        file.name.endsWith(".json");
      const contentType = isJson ? "application/json" : "text/csv";
      const body = await file.text();

      const url = buildUrl("/api/ingest", {
        source_name: String(sourceName || "demo-source"),
        default_metric: String(metric || "events_total"),
      });
      const js = await request<any>(url, {
        method: "POST",
        headers: { "Content-Type": contentType },
        body,
      });
      if (js?.ok === false) {
        throw new Error(js?.error?.message || "Upload failed");
      }

      await postJson("/api/kpi/run", {
        source_name: sourceName,
        metric,
      }).catch(() => {});

      setUploadMsg(
        `Ingested ${js?.data?.ingested_rows ?? js?.ingested_rows ?? "?"} rows` +
          (js?.duplicates ? `, ${js.duplicates} duplicates` : "") +
          ` (${file.name}).`,
      );

      setEnd((e) => e); // nudge base effect
      void loadMetricNames(sourceName); // refresh metric list
    } catch (e: any) {
      setUploadMsg(e?.message || "Upload failed.");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function onExportPng() {
    if (!exportRef.current) return;
    const dataUrl = await toPng(exportRef.current, {
      backgroundColor: "white",
      pixelRatio: 2,
      cacheBust: true,
      filter: (node) => {
        return !(
          node instanceof Element &&
          node.getAttribute &&
          node.getAttribute("data-export-ignore") === "true"
        );
      },
    });
    const fname = `dashboard_${sourceName}_${metric}_${start}_${end}.png`;
    saveAs(dataUrl, fname);
  }

  async function onExportCsv() {
    try {
      const url = buildUrl("/api/metrics/export/csv", {
        source_name: String(sourceName),
        metric: String(metric),
        start,
        end,
      });
      const resp = await fetch(url, {
        headers: withAuthHeaders(),
      });
      if (!resp.ok) {
        const text = await resp.text().catch(() => "");
        throw new Error(text || `Export failed (HTTP ${resp.status})`);
      }
      const blob = await resp.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `metric_${metric}_${sourceName}_${start}_${end}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Export failed");
    }
  }

  function handleSignOut() {
    authApi.logout();
    window.location.replace("/");
  }

  /* ---------- Reset handler ---------- */
  function handleReset() {
    const newStart = isoDaysAgo(6);
    const newEnd = isoDaysAgo(0);
    setSourceName("demo-source");
    setMetric("events_total");
    setDateRange("7");
    setStart(newStart);
    setEnd(newEnd);
    setShowAnoms(false);
    setShowForecast(false);
    setWindowN(7);
    setZThresh(3);
  }

  /* ---------- chart remount key ---------- */
  const chartKey = useMemo(
    () =>
      `${sourceName}|${metric}|${start}|${end}|${showAnoms}|${showForecast}`,
    [sourceName, metric, start, end, showAnoms, showForecast],
  );

  // Filters UI
  const filters = (
    <FiltersBar
      Source={
        <select
          key={sourceNamesKey}
          data-testid="filter-source"
          value={sourceName || ""}
          onChange={(e) => setSourceName(e.target.value)}
          aria-label="Source"
        >
          {sources.length === 0 ? (
            <option value="" disabled>
              (no sources yet)
            </option>
          ) : (
            sources.map((s) => (
              <option key={s.id ?? s.name} value={s.name}>
                {s.name}
              </option>
            ))
          )}
        </select>
      }
      Metric={
        <select
          data-testid="filter-metric"
          value={metric}
          onChange={(e) => setMetric(e.target.value)}
          aria-label="Metric"
        >
          {(metricOptions.length ? metricOptions : ["events_total"]).map(
            (m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ),
          )}
        </select>
      }
      Start={
        <input
          data-testid="filter-start"
          type="date"
          value={start}
          onChange={(e) => setStart(e.target.value)}
          max={end || undefined}
          aria-label="Start date"
        />
      }
      End={
        <input
          data-testid="filter-end"
          type="date"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
          min={start || undefined}
          aria-label="End date"
        />
      }
      Apply={
        <button
          data-testid="btn-run"
          className="sd-btn"
          onClick={() => {
            setEnd((e) => e); // manual re-run
          }}
          disabled={loading}
        >
          {loading ? "Running…" : "Run"}
        </button>
      }
      Reset={
        <button
          data-testid="btn-reset"
          className="sd-btn ghost"
          disabled={loading}
          onClick={handleReset}
        >
          Reset
        </button>
      }
      SignOut={
        <button
          data-testid="btn-signout"
          className="sd-btn"
          type="button"
          onClick={handleSignOut}
        >
          Sign out
        </button>
      }
      Extra={
        <div className="sd-stack row" style={{ gap: 10, alignItems: "center" }}>
          <select
            data-testid="quick-range"
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value as any)}
            aria-label="Quick range"
          >
            <option value="7">Last 7 days</option>
            <option value="14">Last 14 days</option>
            <option value="30">Last 30 days</option>
          </select>

          <label className="small sd-muted">Window</label>
          <input
            data-testid="anoms-window"
            type="number"
            min={3}
            max={60}
            value={windowN}
            onChange={(e) =>
              setWindowN(Math.max(3, Math.min(60, Number(e.target.value) || 7)))
            }
            style={{ width: 64 }}
            aria-label="Rolling window days"
          />

          <label className="small sd-muted">z≥</label>
          <input
            data-testid="anoms-z"
            type="number"
            step="0.1"
            min={0}
            max={6}
            value={zThresh}
            onChange={(e) =>
              setZThresh(Math.max(0, Math.min(6, Number(e.target.value) || 3)))
            }
            style={{ width: 64 }}
            aria-label="Z-score threshold"
          />

          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input
              data-testid="toggle-anoms"
              type="checkbox"
              checked={showAnoms}
              onChange={(e) => setShowAnoms(e.target.checked)}
            />
            Show anomalies
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input
              data-testid="toggle-forecast"
              type="checkbox"
              checked={showForecast}
              onChange={(e) => {
                const v = e.target.checked;
                setShowForecast(v);
                if (v) setFcTick((t) => t + 1);
                else setForecast([]);
              }}
            />
            Show forecast
          </label>

          {/* Forecast Reliability badge */}
          <span aria-hidden="true" style={{ width: 1, height: 24, background: "#e5e7eb" }} />
          <div style={{ display: "flex", alignItems: "center" }}>
            <ReliabilityBadge
              compact
              score={rel?.score ?? null}
              grade={(rel?.grade as any) ?? undefined}
              loading={relLoading}
              error={relError ?? null}
              onClick={() => setDrawerOpen(true)}
            />
          </div>

          {/* Export buttons */}
          <button
            type="button"
            className="sd-btn ghost"
          onClick={() => void onExportPng()}
            data-testid="btn-export-png"
          >
            Export PNG
          </button>
          <button
            type="button"
            className="sd-btn ghost"
            onClick={() => void onExportCsv()}
            data-testid="btn-export-csv"
          >
            Export CSV
          </button>

          {/* Upload */}
          <input
            ref={fileRef}
            type="file"
            accept=".csv,application/json,text/csv,application/vnd.ms-excel"
            style={{ display: "none" }}
            onChange={(e) => handleUpload(e.target.files?.[0] ?? null)}
            data-testid="upload-file"
          />
          <button
            type="button"
            className="sd-btn"
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? "Uploading…" : "Upload CSV or JSON"}
          </button>
          {uploadMsg && (
            <span className="sd-text-xs sd-muted" aria-live="polite">
              {uploadMsg}
            </span>
          )}
        </div>
      }
    />
  );

  return (
    <DashboardShell
      headerRight={null}
      filters={filters}
      tiles={<KpiTiles kpis={kpis} />}
      exportRef={exportRef}
      left={
        <div>
          <Text variant="h3">Daily KPIs ({metric})</Text>
          {error && (
            <Text variant="small" className="sd-my-2" muted>
              ⚠️ {error}
            </Text>
          )}
          {rows.length === 0 ? (
            <Text className="sd-my-2" muted>
              No data for this selection. Try a wider range.
            </Text>
          ) : (
            <div className="sd-my-2">
              <MetricDailyChart
                key={chartKey}
                rows={rows.map((r) => ({
                  date: getDate(r) || "",
                  value: num(pick(r, "value_sum", "sum", "total", "value")),
                }))}
                anomalies={anoms}
                forecast={forecast}
              />
              {/* hidden lists for test hooks */}
              <ul data-testid="anomaly-list" style={{ display: "none" }}>
                {anoms.map((a, i) => (
                  <li
                    key={i}
                    data-date={a.date}
                    data-value={a.value}
                    data-z={a.z ?? ""}
                  />
                ))}
              </ul>
              <ul data-testid="forecast-list" style={{ display: "none" }}>
                {forecast.map((p, i) => (
                  <li key={i} data-date={p.date} data-yhat={p.yhat} />
                ))}
              </ul>
            </div>
          )}
        </div>
      }
      right={<MetricDailyTableView rows={rows} />}
    >
      <DetailsDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        details={rel ?? undefined}
      />
    </DashboardShell>
  );
}
