import React, { useEffect, useState } from "react";
import { Card, Text } from "../../ui";
import { getJson } from "../../lib/api";

type Row = {
  metric_date?: string; date?: string; day?: string;
  source?: string; source_id?: number | string;
  metric?: string; name?: string;
  value_sum?: number; sum?: number; total?: number; value?: number;
  value_avg?: number; avg?: number; mean?: number; average?: number;
  value_count?: number; count?: number; rows?: number; n?: number;
  value_distinct?: number; distinct?: number; unique?: number;
};

export default function MetricDailyTable({
  sourceName = "demo-source",
  metric = "events_total",
  start,
  end,
  distinctField = ""
}: {
  sourceName?: string;
  metric?: string;
  start?: string;
  end?: string;
  distinctField?: string;
}) {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        setError(null);
        const params: Record<string, string> = {
          source_name: String(sourceName),
          metric: String(metric),
        };
        if (start) params.start_date = start;
        if (end) params.end_date = end;
        if (distinctField) params.distinct_field = distinctField;

        const js = await getJson<any>("/api/metrics/daily", params);
        const arr: Row[] = Array.isArray(js) ? js : js.items ?? js.data ?? [];
        arr.sort((a, b) => (getDate(a) || "").localeCompare(getDate(b) || ""));
        setRows(arr);
      } catch (e: any) {
        setRows([]);
        setError(e?.message || "Failed to load table");
      } finally {
        setLoading(false);
      }
    })();
  }, [sourceName, metric, start, end, distinctField]);

  return (
    <Card>
      <Text variant="h3">MetricDaily Table</Text>
      {error && <Text variant="small" className="sd-my-2" muted>⚠️ {error}</Text>}
      <div className="sd-border" style={{ borderRadius: 10, overflow: "hidden", marginTop: 8 }}>
        <table style={{ borderCollapse: "collapse", width: "100%" }}>
          <thead>
            <tr>
              {["Date","Source","Metric","Sum","Avg","Count","Distinct"].map(h => (
                <th key={h} style={thTd(true)}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const date = getDate(r);
              return (
                <tr key={`${date}-${i}`}>
                  <td style={thTd()}>{fmt(date)}</td>
                  <td style={thTd()}>{fmt(r.source ?? r.source_id)}</td>
                  <td style={thTd()}>{fmt(r.metric ?? r.name)}</td>
                  <td style={thTd()}>{fmt(r.value_sum ?? r.sum ?? r.total ?? r.value)}</td>
                  <td style={thTd()}>{fmt(r.value_avg ?? r.avg ?? r.mean ?? r.average)}</td>
                  <td style={thTd()}>{fmt(r.value_count ?? r.count ?? r.rows ?? r.n)}</td>
                  <td style={thTd()}>{fmt(r.value_distinct ?? r.distinct ?? r.unique)}</td>
                </tr>
              );
            })}
            {!loading && rows.length === 0 && (
              <tr><td style={thTd()} colSpan={7}>No data for selected range.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function getDate(r: Row) { return (r.metric_date ?? r.date ?? r.day) as string | undefined; }
function fmt(v: any) { return v === undefined || v === null || v === "" ? "—" : String(v); }
function thTd(header = false): React.CSSProperties {
  return {
    border: "1px solid #2a2a2a",
    padding: "8px 10px",
    textAlign: "left",
    background: header ? "#111" : "transparent",
  };
}
