import React from "react";
import { Card, Grid, Stack, Text } from "../../ui";

export type DashboardShellProps = {
  headerRight?: React.ReactNode;
  filters?: React.ReactNode;
  left?: React.ReactNode;
  right?: React.ReactNode;
  footer?: React.ReactNode;
  tiles?: React.ReactNode;
  children?: React.ReactNode;
};

export const DashboardShell: React.FC<DashboardShellProps> = ({
  headerRight,
  filters,
  left,
  right,
  footer,
  tiles,
  children,
}) => {
  return (
    <>
      <Stack className="sd-my-4" gap="md">
        <Card elevation={1}>
          <Stack direction="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <Text as="h1" variant="h2">Smart Data Pipeline — Dashboard</Text>
            <div>{headerRight}</div>
          </Stack>
          {filters ? <div className="sd-my-2">{filters}</div> : null}
        </Card>

        {tiles ? (
          <Stack direction="row" style={{ flexWrap: "wrap" }}>
            {tiles}
          </Stack>
        ) : null}

        <Grid columns={12} className="sd-my-2">
          <Card className="sd-card" style={{ gridColumn: "span 7" }}>
            {left}
          </Card>
          <Card className="sd-card" style={{ gridColumn: "span 5" }}>
            {right}
          </Card>
        </Grid>

        {footer ? <div className="sd-my-2">{footer}</div> : null}
      </Stack>

      {children}
    </>
  );
};

export default DashboardShell;
