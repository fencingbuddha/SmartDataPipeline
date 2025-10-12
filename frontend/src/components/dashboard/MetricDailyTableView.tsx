import React from "react";
import { Card, Text } from "../../ui";

type Row = {
  metric_date?: string; date?: string; day?: string;
  source_id?: number | string; source?: string;
  metric?: string; name?: string;
  value_sum?: number; sum?: number; total?: number; value?: number;
  value_avg?: number; avg?: number; mean?: number; average?: number;
  value_count?: number; count?: number; rows?: number; n?: number;
  value_distinct?: number; distinct?: number; unique?: number;
};

export default function MetricDailyTableView({ rows }: { rows: Row[] }) {
  return (
    <Card>
      <Text variant="h3">MetricDaily Table</Text>
      <div className="sd-border" style={{ borderRadius: 10, overflow: "hidden", marginTop: 8 }}>
        <table style={{ borderCollapse: "collapse", width: "100%" }}>
          <thead>
            <tr>
              {["Date","Source","Metric","Sum","Avg","Count","Distinct"].map((h) => (
                <th key={h} style={thTd(true)}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={`${getDate(r)}-${i}`}>
                <td style={thTd()}>{fmt(getDate(r))}</td>
                <td style={thTd()}>{fmt(r.source ?? r.source_id)}</td>
                <td style={thTd()}>{fmt(r.metric ?? r.name)}</td>
                <td style={thTd()}>{fmt(r.value_sum ?? r.sum ?? r.total ?? r.value)}</td>
                <td style={thTd()}>{fmt(r.value_avg ?? r.avg ?? r.mean ?? r.average)}</td>
                <td style={thTd()}>{fmt(r.value_count ?? r.count ?? r.rows ?? r.n)}</td>
                <td style={thTd()}>{fmt(r.value_distinct ?? r.distinct ?? r.unique)}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td style={thTd()} colSpan={7}>No data for this selection.</td></tr>
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
