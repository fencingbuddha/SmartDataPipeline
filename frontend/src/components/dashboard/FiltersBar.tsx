import React from "react";
import { Stack, Text } from "../../ui";

export type FiltersBarProps = {
  Source: React.ReactNode;
  Metric: React.ReactNode;
  Start: React.ReactNode;
  End: React.ReactNode;
  Distinct?: React.ReactNode;
  Apply: React.ReactNode;
  Reset: React.ReactNode;
  Extra?: React.ReactNode;
};

export const Labeled: React.FC<React.PropsWithChildren<{ label: string }>> = ({ label, children }) => (
  <div className="sd-stack col" style={{ gap: 4 }}>
    <Text variant="small" muted>{label}</Text>
    {children}
  </div>
);

export const FiltersBar: React.FC<FiltersBarProps> = (p) => {
  return (
    <Stack direction="row" gap="md" style={{ flexWrap: "wrap", alignItems: "end" }}>
      <Labeled label="Source">{p.Source}</Labeled>
      <Labeled label="Metric">{p.Metric}</Labeled>
      <Labeled label="Start">{p.Start}</Labeled>
      <Labeled label="End">{p.End}</Labeled>
      {p.Distinct ? <Labeled label="Distinct Field (opt)">{p.Distinct}</Labeled> : null}
      {p.Apply}
      {p.Reset}
      {p.Extra}
    </Stack>
  );
};

export default FiltersBar;
