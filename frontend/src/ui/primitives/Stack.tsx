import React from "react";

export type StackProps = React.HTMLAttributes<HTMLDivElement> & {
  direction?: "row" | "col";
  gap?: "sm" | "md" | "lg";
  align?: "start" | "center" | "end" | "stretch";
  justify?: "start" | "center" | "end" | "between";
};

const gapClass = (g?: StackProps["gap"]) => {
  switch (g) {
    case "sm": return "sd-gap-2";
    case "lg": return "sd-gap-6";
    case "md":
    default: return "sd-gap-4";
  }
};

export const Stack: React.FC<StackProps> = ({ className = "", direction = "col", gap = "md", style, align, justify, ...rest }) => {
  const dir = direction === "row" ? "row" : "col";
  const s: React.CSSProperties = {
    display: "flex",
    flexDirection: direction === "row" ? "row" : "column",
    alignItems: align === "center" ? "center" : align === "end" ? "flex-end" : align === "stretch" ? "stretch" : "flex-start",
    justifyContent: justify === "center" ? "center" : justify === "end" ? "flex-end" : justify === "between" ? "space-between" : "flex-start",
    ...(style || {}),
  };
  return <div className={`sd-stack ${dir} ${gapClass(gap)} ${className}`.trim()} style={s} {...rest} />;
};

export default Stack;
