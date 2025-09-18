import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

export default function MetricDailyChart({ rows }: { rows: {metric_date:string; value:number}[] }) {
  const data = rows.map(r => ({ date: r.metric_date, value: r.value }));
  return (
    <div style={{ height: 280, marginTop: 12, border: "1px solid #eee", borderRadius: 8, padding: 8 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey="value" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
