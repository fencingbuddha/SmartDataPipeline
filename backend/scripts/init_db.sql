-- Sources
CREATE TABLE IF NOT EXISTS sources (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- RawEvents
CREATE TABLE IF NOT EXISTS raw_events (
  id BIGSERIAL PRIMARY KEY,
  source_id INT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  event_timestamp TIMESTAMP NOT NULL,
  payload JSONB NOT NULL,
  ingestion_batch TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_raw_events_source ON raw_events(source_id);
CREATE INDEX IF NOT EXISTS idx_raw_events_time   ON raw_events(event_timestamp);

-- CleanEvents
CREATE TABLE IF NOT EXISTS clean_events (
  id BIGSERIAL PRIMARY KEY,
  source_id INT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  event_date DATE NOT NULL,
  event_timestamp TIMESTAMP,
  metric_name TEXT,
  value NUMERIC(18,6),
  dimensions JSONB,
  raw_event_id BIGINT REFERENCES raw_events(id),
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_clean_events_source_date ON clean_events(source_id, event_date);

-- MetricDaily
CREATE TABLE IF NOT EXISTS metric_daily (
  metric_date DATE NOT NULL,
  source_id   INT  NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  metric_name TEXT NOT NULL,
  value       NUMERIC(18,6) NOT NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
  PRIMARY KEY (metric_date, source_id, metric_name)
);

-- Alerts
CREATE TABLE IF NOT EXISTS alerts (
  id BIGSERIAL PRIMARY KEY,
  metric_date DATE NOT NULL,
  source_id   INT  NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  metric_name TEXT NOT NULL,
  severity    TEXT NOT NULL CHECK (severity IN ('low','medium','high')),
  method      TEXT,
  score       NUMERIC(18,6),
  message     TEXT,
  created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_alerts_lookup ON alerts(metric_date, source_id, metric_name);

-- ForecastResults
CREATE TABLE IF NOT EXISTS forecast_results (
  forecast_date DATE NOT NULL,
  source_id     INT  NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  metric_name   TEXT NOT NULL,
  yhat          NUMERIC(18,6) NOT NULL,
  yhat_lower    NUMERIC(18,6),
  yhat_upper    NUMERIC(18,6),
  model_version TEXT,
  created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
  PRIMARY KEY (forecast_date, source_id, metric_name)
);
