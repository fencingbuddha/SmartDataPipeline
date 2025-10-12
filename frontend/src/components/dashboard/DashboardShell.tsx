import React from "react";
import { Card, Grid, Stack, Tile, Text } from "../../ui";

export type DashboardShellProps = {
  headerRight?: React.ReactNode;
  filters?: React.ReactNode;
  left?: React.ReactNode;
  right?: React.ReactNode;
  footer?: React.ReactNode;
  tiles?: React.ReactNode;
};

export const DashboardShell: React.FC<DashboardShellProps> = (props) => {
  return (
    <Stack className="sd-my-4" gap="md">
      <Card elevation={1}>
        <Stack direction="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <Text as="h1" variant="h2">Smart Data Pipeline — Dashboard</Text>
          <div>{props.headerRight}</div>
        </Stack>
        {props.filters ? <div className="sd-my-2">{props.filters}</div> : null}
      </Card>

      {props.tiles ? (
        <Stack direction="row" style={{ flexWrap: "wrap" }}>
          {props.tiles}
        </Stack>
      ) : null}

      <Grid columns={12} className="sd-my-2">
        <Card className="sd-card" style={{ gridColumn: "span 7" }}>
          {props.left}
        </Card>
        <Card className="sd-card" style={{ gridColumn: "span 5" }}>
          {props.right}
        </Card>
      </Grid>

      {props.footer ? <div className="sd-my-2">{props.footer}</div> : null}
    </Stack>
  );
};

export default DashboardShell;
