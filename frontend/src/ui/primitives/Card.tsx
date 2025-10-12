import React from "react";

export type CardProps = React.HTMLAttributes<HTMLDivElement> & {
  padding?: "none" | "sm" | "md" | "lg";
  elevation?: 0 | 1 | 2;
};

const padClass = (p?: CardProps["padding"]) => {
  switch (p) {
    case "none": return "sd-p-0";
    case "sm": return "sd-p-2";
    case "lg": return "sd-p-6";
    case "md":
    default: return "sd-p-4";
  }
};

export const Card: React.FC<CardProps> = ({ className = "", padding = "md", elevation = 1, ...rest }) => {
  const elev = elevation === 0 ? "elev-0" : elevation === 2 ? "elev-2" : "";
  return <div className={`sd-card ${padClass(padding)} ${elev} ${className}`.trim()} {...rest} />;
};

export default Card;
