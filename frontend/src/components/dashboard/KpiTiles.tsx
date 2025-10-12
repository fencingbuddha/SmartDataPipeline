import React from "react";
import { Tile, Text, Stack } from "../../ui";

export type Kpis = { sum: number; avg: number; count: number; distinct?: number | null; hasDistinct?: boolean };
export const KpiTiles: React.FC<{ kpis: Kpis }> = ({ kpis }) => {
  return (
    <Stack direction="row" style={{ flexWrap: "wrap" }}>
      <Tile title="Sum"><Text variant="h3">{fmt(kpis.sum)}</Text></Tile>
      <Tile title="Average"><Text variant="h3">{fmt(kpis.avg)}</Text></Tile>
      <Tile title="Count"><Text variant="h3">{fmt(kpis.count)}</Text></Tile>
      <Tile title="Distinct"><Text variant="h3">{kpis.hasDistinct ? fmt(kpis.distinct) : "—"}</Text></Tile>
    </Stack>
  );
};

function fmt(v: any) {
  return typeof v === "number" && Number.isFinite(v) ? v.toString() : "—";
}

export default KpiTiles;
