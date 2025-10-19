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
type ForecastPoint = { date: string; yhat: number };
type Anomaly = { date: string; value: number; z?: number };

type MergedPoint = {
  date: string;
  value?: number;
  yhat?: number;
  __anom?: boolean;
};

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
  const data: MergedPoint[] = useMemo(() => {
    const map = new Map<string, MergedPoint>();
    for (const r of rows ?? []) map.set(r.date, { date: r.date, value: r.value, __anom: false });
    for (const f of forecast ?? []) {
      const prev = map.get(f.date) ?? { date: f.date, __anom: false };
      prev.yhat = f.yhat;
      map.set(f.date, prev);
    }
    const anomDates = new Set((anomalies ?? []).map(a => a.date));
    const merged = Array.from(map.values()).map(d => ({ ...d, __anom: d.__anom || anomDates.has(d.date) }));
    merged.sort((a, b) => a.date.localeCompare(b.date));
    return merged;
  }, [rows, forecast, anomalies]);

  const fmtDate = (d: string) =>
    new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric" });

  const hasForecast = Array.isArray(forecast) && forecast.length > 0;

  // Disable Recharts animations so the line renders fully on first paint
  const NO_ANIM = { isAnimationActive: false, animationDuration: 0 } as const;

  return (
    <div data-testid="chart" style={{ position: "relative", width: "100%", height }}>
      <ResponsiveContainer>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" tickFormatter={fmtDate} minTickGap={24} />
          <YAxis label={{ value: yLabel, angle: -90, position: "insideLeft" }} />
          <Tooltip
            labelFormatter={fmtDate}
            formatter={(v: any, n: string) => [v, n === "value" ? "Actual" : n === "yhat" ? "Forecast" : n]}
          />

          {/* Actual series — animation OFF */}
          <Line
            {...NO_ANIM}
            type="monotone"
            dataKey="value"
            name="Actual"
            strokeWidth={2}
            connectNulls
            activeDot={false}
            // static dot: only render anomaly points (no animation)
            dot={({ cx, cy, payload }: any) =>
              payload?.__anom ? <circle cx={cx} cy={cy} r={4} fill="#dc2626" /> : <g />
            }
          />

          {/* Forecast series — animation OFF */}
          {hasForecast ? (
            <Layer>
              <Line
                {...NO_ANIM}
                type="monotone"
                dataKey="yhat"
                name="Forecast"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
                connectNulls
              />
            </Layer>
          ) : null}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
