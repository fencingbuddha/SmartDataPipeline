import React from "react";
import { Card, Stack, Tile, Text } from "../../ui";

export const UploadWidget: React.FC<{
  dropzone: React.ReactNode;
  recentUploads: React.ReactNode;
  helper?: React.ReactNode;
  banner?: { kind: "success" | "error"; message: string } | null;
}> = ({ dropzone, recentUploads, helper, banner }) => {
  return (
    <Card elevation={1}>
      <Stack direction="row" style={{ alignItems: "stretch", flexWrap: "wrap" }}>
        <Tile title="Drag & drop files" className="sd-stack col" style={{ flex: 1, minWidth: 300 }}>
          {dropzone}
          <Text variant="small" muted className="sd-my-2">{helper}</Text>
        </Tile>
        <Tile title="Recent uploads" className="sd-stack col" style={{ flex: 1, minWidth: 300 }}>
          {recentUploads}
        </Tile>
      </Stack>
      {banner ? (
        <div className="sd-my-2" style={{
          border: "1px solid",
          borderColor: banner.kind === "success" ? "var(--sd-color-success)" : "var(--sd-color-danger)",
          padding: 12,
          borderRadius: 8
        }}>
          <Text>{banner.message}</Text>
        </div>
      ) : null}
    </Card>
  );
};

export default UploadWidget;
