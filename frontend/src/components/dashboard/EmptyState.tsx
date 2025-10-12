import React from "react";
import { Card, Text } from "../../ui";

export const EmptyState: React.FC<{ title?: string; body?: React.ReactNode }> = ({ title = "No data for selected range.", body }) => {
  return (
    <Card elevation={1}>
      <Text variant="h3">{title}</Text>
      <Text className="sd-my-2" muted>{body ?? "Adjust date range, source, or metric to see results."}</Text>
    </Card>
  );
};

export default EmptyState;
