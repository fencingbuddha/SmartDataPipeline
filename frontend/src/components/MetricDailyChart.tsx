import { useMemo } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Layer,
} from "recharts";

type Point = { date: string; value: number };
type ForecastPoint = { date: string; yhat: number; yhatLo?: number; yhatHi?: number };
type Anomaly = { date: string; value: number; z?: number };

function toTS(d: string): number | null {
  const t = Date.parse(d);
  return Number.isFinite(t) ? t : null;
}

export default function MetricDailyChart({
  rows,
  forecast = [],
  anomalies = [],
  height = 320,
  yLabel = "Value",
}: {
  rows: Point[];
  forecast?: ForecastPoint[];
  anomalies?: Anomaly[];
  height?: number;
  yLabel?: string;
}) {
  // Normalize + timestamp both series
  const actualWithTs = useMemo(
    () =>
      (rows ?? [])
        .map((r) => ({ ...r, ts: toTS(r.date) }))
        .filter((r) => r.ts !== null) as Array<Point & { ts: number }>,
    [rows]
  );

  const forecastWithTs = useMemo(
    () =>
      (forecast ?? [])
        .map((f: any) => {
          const date =
            String(f.date ?? f.forecast_date ?? f.target_date ?? f.metric_date ?? "");
          return {
            date,
            yhat: Number(f.yhat ?? f.value ?? f.y ?? NaN),
            yhatLo: f.yhat_lo ?? f.yhat_lower,
            yhatHi: f.yhat_hi ?? f.yhat_upper,
            ts: toTS(date),
          };
        })
        .filter((f) => f.ts !== null && Number.isFinite(f.yhat)) as Array<
        ForecastPoint & { ts: number }
      >,
    [forecast]
  );

  // Build a union X-domain from timestamps so future points render in the right place
  const xDomainData = useMemo(() => {
    const set = new Set<number>();
    for (const r of actualWithTs) set.add(r.ts);
    for (const f of forecastWithTs) set.add(f.ts);
    return Array.from(set)
      .sort((a, b) => a - b)
      .map((ts) => ({ ts }));
  }, [actualWithTs, forecastWithTs]);

  const anomTS = useMemo(
    () => new Set((anomalies ?? []).map((a) => toTS(a.date)!).filter((t) => t !== null)),
    [anomalies]
  );

  const fmtDate = (t: number) =>
    new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" });

  const NO_ANIM = { isAnimationActive: false, animationDuration: 0 } as const;

  return (
    <div data-testid="chart" style={{ position: "relative", width: "100%", height }}>
      <ResponsiveContainer>
        {/* Use numeric time scale for perfect alignment */}
        <LineChart data={xDomainData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="ts"
            type="number"
            domain={["dataMin", "dataMax"]}
            tickFormatter={fmtDate}
            minTickGap={24}
          />
          <YAxis label={{ value: yLabel, angle: -90, position: "insideLeft" }} />
          <Tooltip
            labelFormatter={(t) => fmtDate(Number(t))}
            formatter={(v: any, n: string) => [v, n === "value" ? "Actual" : n === "yhat" ? "Forecast" : n]}
          />

          {/* Actuals */}
          <Line
            {...NO_ANIM}
            name="Actual"
            type="monotone"
            data={actualWithTs}
            dataKey="value"
            xAxisId={0}
            key="ts"
            strokeWidth={2}
            connectNulls
            activeDot={false}
            dot={({ cx, cy, payload }: any) =>
              payload?.ts && anomTS.has(payload.ts) ? (
                <circle cx={cx} cy={cy} r={4} fill="#dc2626" />
              ) : (
                <g />
              )
            }
          />

          {/* Forecast (dashed) */}
          {forecastWithTs.length > 0 && (
            <Layer>
              <Line
                {...NO_ANIM}
                name="Forecast"
                type="monotone"
                data={forecastWithTs}
                dataKey="yhat"
                xAxisId={0}
                key="ts"
                strokeDasharray="6 4"
                dot={false}
                connectNulls
                strokeOpacity={0.95}
              />
            </Layer>
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
