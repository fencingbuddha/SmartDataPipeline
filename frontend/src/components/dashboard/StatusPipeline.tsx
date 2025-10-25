import React from "react";
import { Card, Stack, Tile, Text } from "../../ui";

export type Stage = { title: string; subtitle?: string; value?: React.ReactNode };
export const StatusPipeline: React.FC<{ stages: Stage[]; footer?: React.ReactNode }> = ({ stages, footer }) => {
  return (
    <Card elevation={1}>
      <Text variant="h3">Ingestion Status</Text>
      <Stack direction="row" className="sd-my-2" style={{ flexWrap: "wrap" }}>
        {stages.map((s, i) => (
          <Tile key={i} title={s.title} subtitle={s.subtitle}>
            <Text variant="h3">{s.value ?? "—"}</Text>
          </Tile>
        ))}
      </Stack>
      {footer}
    </Card>
  );
};

export default StatusPipeline;
