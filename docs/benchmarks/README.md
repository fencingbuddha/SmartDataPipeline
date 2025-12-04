# QR-1 Performance Benchmarks

This folder contains raw evidence used to validate QR-1 (response time).

- `qr1_curl_timings.txt` – manual `curl` measurements captured on 2025-11-11 from the portable ZIP demo, showing sub-2ms responses for `/health`, `/api/metrics/daily`, and `/api/forecast`.
- `qr1_prom_metrics.txt` – Prometheus metrics snapshot from the same session. The `http_request_duration_seconds_*` histograms show:
  - `/api/auth/login`: 44 logins, all under 0.5s (≈90% under 0.25s).
  - KPI, anomaly, forecast reliability, and export endpoints: all requests in the sub-100ms range.
  
These artifacts are referenced in the Week 14 assessment to demonstrate that SmartDataPipeline meets the QR-1 latency requirement under typical demo load.