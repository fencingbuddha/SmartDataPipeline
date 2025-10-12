import React from "react";

export type GridProps = React.HTMLAttributes<HTMLDivElement> & {
  columns?: number; // 1..12
  gap?: "sm" | "md" | "lg";
};

const gapClass = (g?: GridProps["gap"]) => {
  switch (g) {
    case "sm": return "sd-gap-2";
    case "lg": return "sd-gap-6";
    case "md":
    default: return "sd-gap-4";
  }
};

export const Grid: React.FC<GridProps> = ({ className = "", columns = 12, gap = "md", style, ...rest }) => {
  const gridStyle: React.CSSProperties = { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`, ...(style || {}) };
  return <div className={`sd-grid ${gapClass(gap)} ${className}`.trim()} style={gridStyle} {...rest} />;
};

export default Grid;
