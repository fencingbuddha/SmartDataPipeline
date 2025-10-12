import React from "react";

export type TextProps = React.HTMLAttributes<HTMLElement> & {
  as?: keyof JSX.IntrinsicElements;
  variant?: "h1" | "h2" | "h3" | "body" | "small" | "mono";
  muted?: boolean;
};

export const Text: React.FC<TextProps> = ({ as = "span", variant = "body", muted = false, className = "", ...rest }) => {
  const Tag: any = as;
  const variantClass =
    variant === "h1" ? "h1 sd-heading" :
    variant === "h2" ? "h2 sd-heading" :
    variant === "h3" ? "h3 sd-heading" :
    variant === "small" ? "small" :
    variant === "mono" ? "mono" :
    "";
  const mutedClass = muted ? "sd-muted" : "";
  return <Tag className={`${variantClass} ${mutedClass} ${className}`.trim()} {...rest} />;
};

export default Text;
