import { ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip } from "recharts";
import dayjs from "dayjs";

export type ChartPoint = { date: string; value: number };

export default function MetricDailyChart({ data }: { data: ChartPoint[] }) {
  const safeData = Array.isArray(data) ? data : [];

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={safeData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tickFormatter={(d) => dayjs(d).format("MM-DD")} minTickGap={24} />
        <YAxis allowDecimals={false} />
        <Tooltip
          labelFormatter={(v) => dayjs(v as string).format("YYYY-MM-DD")}
          formatter={(val) => [String(val), "Value"] as [string, string]}
        />
        <Line type="monotone" dataKey="value" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
