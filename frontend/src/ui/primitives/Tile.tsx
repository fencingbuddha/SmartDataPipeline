import React from "react";

export type TileProps = React.HTMLAttributes<HTMLDivElement> & {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
};

export const Tile: React.FC<TileProps> = ({ className = "", title, subtitle, actions, children, ...rest }) => {
  return (
    <div className={`sd-tile ${className}`.trim()} {...rest}>
      {(title || actions || subtitle) && (
        <div className="sd-stack row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
          <div>
            {title ? <div className="h3 sd-heading">{title}</div> : null}
            {subtitle ? <div className="small sd-muted">{subtitle}</div> : null}
          </div>
          {actions ? <div className="sd-stack row" style={{ gap: 8 }}>{actions}</div> : null}
        </div>
      )}
      {children}
    </div>
  );
};

export default Tile;
