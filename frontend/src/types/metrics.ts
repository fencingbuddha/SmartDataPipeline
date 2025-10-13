export type ISODate = string; // 'YYYY-MM-DD'

export interface MetricDailyRow {
  metric_date: ISODate;
  source: string;
  metric: string;     // e.g., "events_total"
  value_sum?: number | null;
  value_avg?: number | null;
  value_count?: number | null;
  value_distinct?: number | null;
}

export interface AnomalyPoint {
  metric_date: ISODate;
  metric: string;
  source: string;
  value: number;
  z?: number | null;         // rolling z-score
  is_anomaly: boolean;       // true where z > threshold (server or client)
}

export interface ForecastPoint {
  target_date: ISODate;
  metric: string;
  source: string;
  yhat: number;
  yhat_lower?: number | null;
  yhat_upper?: number | null;
}
