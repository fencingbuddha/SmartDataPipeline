import { useMemo, useState, useEffect } from "react";
import MetricDailyChart from "./MetricDailyChart";
import { Card, Stack, Tile, Text } from "../ui";

import { buildUrl } from "../lib/api";
import { useMetricDaily } from "../hooks/useMetricDaily";
import { useAnomalies } from "../hooks/useAnomalies";
import { useForecast } from "../hooks/useForecast";

import MetricDailyView from "./MetricDailyView";

/**
 * KPI card (container) with filters, CSV export, and configurable anomaly/forecast overlays.
 * Data fetching is done here; presentational layout is delegated to MetricDailyView.
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

  /** Toggles */
  const [showAnoms, setShowAnoms] = useState(false);
  const [showForecast, setShowForecast] = useState(false);

  /** Sources & metric names (kept local, simple fetches inline) */
  const [sources, setSources] = useState<Source[]>([]);
  const [metricOptions, setMetricOptions] = useState<string[]>([]);
  const safeSources = useMemo(() => (Array.isArray(sources) ? sources : []), [sources]);

  // Load sources once
  useOnce(async () => {
    try {
      const r = await fetch(buildUrl("/api/sources"));
      const js: any = await r.json();
      const arr: any[] = Array.isArray(js) ? js : js?.data ?? [];
      const data: Source[] = arr.map((s: any) =>
        typeof s === "string" ? { id: s, name: s } : { id: s.id ?? s.name, name: s.name ?? String(s) }
      );
      setSources(data);
      if (data.length && !data.find((s) => s.name === sourceName)) {
        setSourceName(data[0].name);
      }
    } catch {
      setSources([]);
    }
  });

  // Load metric names whenever source changes
  useWhen([sourceName], async () => {
    if (!sourceName) return;
    try {
      const r = await fetch(buildUrl("/api/metrics/names", { source_name: String(sourceName) }));
      if (!r.ok) throw new Error(String(r.status));
      const names: string[] = await r.json();
      setMetricOptions(names);
      if (names.length && !names.includes(metric)) setMetric(names[0]);
    } catch {
      setMetricOptions([]);
    }
  });

  /** === Hooks: data fetching === */
  const {
    data: rowsRaw,
    loading: kpiLoading,
    error: kpiError,
  } = useMetricDaily({
    source_name: sourceName,
    metric,
    start_date: start,
    end_date: end,
    // distinct_field: distinctField || undefined, // enable if your API supports it
  } as any);

  const rows: Row[] = useMemo(() => {
    const arr = Array.isArray(rowsRaw) ? rowsRaw.slice() : [];
    arr.sort((a: any, b: any) => (getDate(a) || "").localeCompare(getDate(b) || ""));
    return arr as Row[];
  }, [rowsRaw]);

  const {
    data: anomsRaw,
    loading: anomsLoading,
    error: anomsError,
  } = useAnomalies(
    {
      source_name: sourceName,
      metric,
      start_date: start,
      end_date: end,
      window: algo === "rolling" ? windowN : undefined,
      z_thresh: algo === "rolling" ? zThresh : undefined,
    },
    showAnoms
  );

  const anomalies = useMemo(
    () =>
      (anomsRaw || []).map((p: any) => ({
        date: String(p.metric_date ?? p.date ?? ""),
        value: Number(p.value ?? 0),
        z: typeof p.z === "number" ? p.z : undefined,
      })),
    [anomsRaw]
  );

  const {
    data: forecastRaw,
    loading: fcLoading,
    error: fcError,
  } = useForecast(
    {
      source_name: sourceName,
      metric,
      start_date: start,
      end_date: end,
    },
    showForecast
  );

  const forecast = useMemo(
    () =>
      (forecastRaw || []).map((p: any) => ({
        date: String(p.target_date ?? p.metric_date ?? p.date ?? ""),
        yhat: Number(p.yhat ?? 0),
      })),
    [forecastRaw]
  );

  /** Export CSV */
  const [exporting, setExporting] = useState(false);
  async function handleExportCSV() {
    if (!sourceName || !metric) return;
    setExporting(true);
    try {
      const url = buildUrl("/api/metrics/export/csv", {
        source_name: String(sourceName),
        metric: String(metric),
        start_date: start,
        end_date: end,
      });
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `metric_daily_${metric}_${sourceName}_${start}_${end}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (e: any) {
      console.error(e);
      alert(e?.message || "Export failed");
    } finally {
      setExporting(false);
    }
  }

  /** KPI tiles (unchanged) */
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

  const anyLoading = kpiLoading || anomsLoading || fcLoading;
  const error = kpiError?.message || anomsError?.message || fcError?.message || null;

  /** ---------- Presentational slots ---------- */

  // 1) Filters (Figma: first)
  const FiltersSection = (
    <Stack
      direction="row"
      className="sd-my-2"
      style={{ flexWrap: "wrap", alignItems: "end" }}
      data-testid="filters-bar"
    >
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
              <option key={s.id ?? s.name} value={s.name}>{s.name}</option>
            ))
          )}
        </select>
      </Labeled>

      <Labeled label="Metric">
        {metricOptions.length ? (
          <select value={metric} onChange={(e) => setMetric(e.target.value)}>
            {metricOptions.map((m) => <option key={m} value={m}>{m}</option>)}
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

      {/* Apply is no longer needed; hooks react to filters. Kept for UX parity */}
      <button onClick={() => { /* no-op; hooks already react */ }} disabled={anyLoading} className="sd-btn" aria-label="Apply filters">
        {anyLoading ? "Loading…" : "Apply"}
      </button>

      <button
        onClick={resetAll}
        disabled={anyLoading}
        className="sd-btn ghost"
        aria-label="Reset filters"
      >
        Reset
      </button>

      <button
        onClick={handleExportCSV}
        disabled={anyLoading || exporting || !metric || !sourceName}
        className="sd-btn"
        aria-label="Export CSV"
      >
        {exporting ? "Exporting…" : "Export CSV"}
      </button>

      <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <input
          type="checkbox"
          aria-label="Show anomalies"
          data-testid="toggle-anomalies"
          checked={showAnoms}
          onChange={(e) => setShowAnoms(e.target.checked)}
          disabled={anyLoading || rows.length === 0}
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
          disabled={anyLoading || rows.length === 0}
        />
        Show forecast
      </label>
    </Stack>
  );

  // 2) Tiles (Figma: second)
  const TilesSection = (
    <Stack direction="row" className="sd-my-2" style={{ flexWrap: "wrap" }} data-testid="kpi-tiles">
      <Tile title="Sum"><Text variant="h3">{fmtNum(kpis.sum)}</Text></Tile>
      <Tile title="Average"><Text variant="h3">{fmtNum(kpis.avg)}</Text></Tile>
      <Tile title="Count"><Text variant="h3">{fmtNum(kpis.count)}</Text></Tile>
      <Tile title="Distinct"><Text variant="h3">{kpis.hasDistinct ? fmtNum(kpis.distinct) : "—"}</Text></Tile>
    </Stack>
  );

  // 3) Table (Figma: third)
  const TableSection = (
    <div className="sd-border" style={{ borderRadius: 10, overflow: "hidden" }} data-testid="metric-table">
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
          {rows.length === 0 && !anyLoading && (
            <tr>
              <td style={thTd()} colSpan={7}>
                No data for this selection. Try a wider date range or different filters.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );

  // 4) Chart (Figma: fourth)
  const ChartSection = rows.length > 0 ? (
    <div className="sd-my-4" aria-busy={anyLoading} data-testid="metric-chart">
      <MetricDailyChart
        key={`${sourceName}-${metric}-${showAnoms ? "A" : "N"}`}
        rows={rows.map((r) => ({
          date: getDate(r) || "",
          value: num(pick(r, "value_sum", "sum", "total", "value")),
        }))}
        anomalies={anomalies}
        forecast={forecast}
      />
    </div>
  ) : (
    <div className="sd-my-4" />
  );

  /** UI (presentational handled by MetricDailyView) */
  return (
    <Card elevation={1} className="sd-my-4">
      <Tile title={`Daily KPIs (${metric})`} />

      <MetricDailyView
        filters={FiltersSection}
        tiles={TilesSection}
        table={TableSection}
        chart={ChartSection}
        isLoading={anyLoading}
        error={error}
        // onRefresh: optional; hooks auto-refresh on param change
        onReset={resetAll}
      />
    </Card>
  );

  /** helpers */
  function resetAll() {
    setMetric(metricOptions[0] ?? "events_total");
    setStart(isoDaysAgo(6));
    setEnd(isoDaysAgo(0));
    setDistinctField("");
    setWindowN(7);
    setZThresh(3);
    setAlgo("rolling");
    setShowAnoms(false);
    setShowForecast(false);
  }
}

/* ---------- tiny effect helpers to avoid boilerplate ---------- */
function useOnce(fn: () => void | Promise<void>) {
  useEffect(() => { void fn(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
}
function useWhen(deps: any[], fn: () => void | Promise<void>) {
  useEffect(() => { void fn(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, deps);
}

/* ---------- local helpers (unchanged) ---------- */
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
function thTd(header = false): React.CSSProperties {
  return {
    border: "1px solid #2a2a2a",
    padding: "8px 10px",
    textAlign: "left",
    background: header ? "#111" : "transparent",
  };
}

function Labeled(props: React.PropsWithChildren<{ label: string; style?: React.CSSProperties }>) {
  return (
    <div className="sd-stack col" style={{ gap: 4, ...props.style }}>
      <Text variant="small" muted>{props.label}</Text>
      {props.children}
    </div>
  );
}
