type Point = { date: string; value: number };
type Anomaly = { date: string; value: number; z?: number };

export default function MetricDailyChart({
  rows,
  anomalies = [],
  height = 260,
  yLabel = "Value",
}: {
  rows: Point[];
  anomalies?: Anomaly[];
  height?: number;
  yLabel?: string;
}) {
  const PAD = { t: 20, r: 16, b: 32, l: 44 };
  const W = Math.max(480, rows.length * 48);
  const H = height;

  // Normalize + sort
  const data = (rows ?? [])
    .filter((d) => isFiniteNum(d.value) && d.date)
    .sort((a, b) => a.date.localeCompare(b.date));

  const xVals = data.map((d) => d.date);
  const yVals = data.map((d) => d.value);
  const xmin = 0;
  const xmax = Math.max(0, xVals.length - 1);
  const ymin = 0;
  const ymax = niceMax(max(yVals), 5);

  // Scales
  const x = (i: number) => PAD.l + (xmax === 0 ? 0 : ((W - PAD.l - PAD.r) * (i - xmin)) / (xmax - xmin));
  const y = (v: number) => H - PAD.b - (ymax === ymin ? 0 : ((H - PAD.t - PAD.b) * (v - ymin)) / (ymax - ymin));

  // Line path
  const path = data.map((d, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(d.value)}`).join(" ");

  // X ticks: first, middle(s), last
  const tickIdxs = pickTicks(xVals.length);
  const ticks = tickIdxs.map((i) => ({ i, label: fmtDateShort(xVals[i]) }));

  // Anomaly overlay — only dates within the series
  const anomPoints = (anomalies ?? [])
    .filter((a) => a.date && xVals.includes(a.date))
    .map((a) => {
      const i = xVals.indexOf(a.date);
      return { x: x(i), y: y(a.value), ...a };
    });

  return (
    <div style={{ overflowX: "auto" }}>
      <svg width={W} height={H} role="img" aria-label="Time series chart">
        {/* Axes */}
        <line x1={PAD.l} y1={PAD.t} x2={PAD.l} y2={H - PAD.b} stroke="#333" />
        <line x1={PAD.l} y1={H - PAD.b} x2={W - PAD.r} y2={H - PAD.b} stroke="#333" />

        {/* Y ticks */}
        {yTicks(ymin, ymax, 5).map((v, k) => (
          <g key={k}>
            <line x1={PAD.l} y1={y(v)} x2={W - PAD.r} y2={y(v)} stroke="#2a2a2a" strokeDasharray="2 4" />
            <text x={PAD.l - 6} y={y(v)} dominantBaseline="middle" textAnchor="end" fill="#9ca3af" fontSize="11">
              {v}
            </text>
          </g>
        ))}

        {/* X ticks */}
        {ticks.map((t, k) => (
          <g key={k}>
            <line x1={x(t.i)} y1={H - PAD.b} x2={x(t.i)} y2={H - PAD.b + 5} stroke="#333" />
            <text x={x(t.i)} y={H - PAD.b + 18} textAnchor="middle" fill="#9ca3af" fontSize="11">
              {t.label}
            </text>
          </g>
        ))}

        {/* Y label */}
        <text x={10} y={PAD.t} fill="#9ca3af" fontSize="11">
          {yLabel}
        </text>

        {/* Line */}
        <path d={path} fill="none" stroke="#6ee7b7" strokeWidth={2} />

        {/* Points */}
        {data.map((d, i) => (
          <circle key={i} cx={x(i)} cy={y(d.value)} r={3} fill="#6ee7b7">
            <title>{`${d.date}: ${d.value}`}</title>
          </circle>
        ))}

        {/* Anomaly overlay: bullseye markers with test hook */}
        {anomPoints.map((p, i) => (
          <g key={`a-${i}`} data-testid="anomaly-point">
            <circle cx={p.x} cy={p.y} r={5} fill="none" stroke="#ef4444" strokeWidth={2} />
            <circle cx={p.x} cy={p.y} r={2.5} fill="#ef4444" />
            <title>{`${p.date} — anomaly${isFiniteNum(p.z) ? ` (z=${p.z!.toFixed(2)})` : ""}: ${p.value}`}</title>
          </g>
        ))}
      </svg>
    </div>
  );
}

/* ---------- utils ---------- */
function max(arr: number[]) { return arr.length ? Math.max(...arr) : 0; }
function niceMax(v: number, step: number) {
  if (!isFiniteNum(v) || v <= 0) return 1;
  return Math.ceil(v / step) * step;
}
function yTicks(min: number, maxv: number, steps: number) {
  if (maxv <= min) return [min];
  const out: number[] = [];
  const step = (maxv - min) / steps;
  for (let i = 0; i <= steps; i++) out.push(Math.round((min + i * step) * 100) / 100);
  return out;
}
function pickTicks(n: number) {
  if (n <= 6) return Array.from({ length: n }, (_, i) => i);
  const idx = new Set<number>([0, n - 1]);
  const mid = Math.floor((n - 1) / 2);
  idx.add(mid);
  idx.add(Math.floor(mid / 2));
  idx.add(Math.floor((mid + n - 1) / 2));
  return Array.from(idx).sort((a, b) => a - b);
}
function isFiniteNum(x: any) { return typeof x === "number" && Number.isFinite(x); }
function fmtDateShort(iso: string) { return iso?.slice(5, 10) || iso; } // "YYYY-MM-DD" -> "MM-DD"
