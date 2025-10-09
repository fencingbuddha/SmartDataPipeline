# User Acceptance Test Summary – Smart Data Pipeline

These User Acceptance Tests (UATs) verify the system’s key end-to-end behaviors from a user’s perspective.  
Each test corresponds directly to a User Story from the product backlog and includes creation and last update dates.

---

### Upload Data → Metrics Visible
- **File:** `test_ingest_to_metrics_ua.py`
- **User Story:** As a user, I can upload event data so that I can view daily metrics on the dashboard.
- **Purpose:** Confirms that uploading a valid CSV through the `/api/upload` endpoint successfully triggers ingestion and that data appears in `/api/metrics/daily`.
- **Created:** October 7, 2025  
- **Last Updated:** October 7, 2025

---

### Forecast Generation → Results Persisted
- **File:** `test_forecast_to_results_ua.py`
- **User Story:** As a user, I can run a forecast for a metric so that predictions are stored and retrievable.
- **Purpose:** Ensures that running `/api/forecast/run` produces forecast entries in the `forecast_results` table and that these records match the requested horizon.
- **Created:** October 7, 2025  
- **Last Updated:** October 7, 2025

---

### Anomaly Overlay → Detectable Outliers
- **File:** `test_anomaly_overlay_ua.py`
- **User Story:** As a user, I can request anomaly overlays for a metric so that outliers are highlighted in visualizations.
- **Purpose:** Verifies that `/api/metrics/anomaly/iforest` responds successfully and returns valid overlay data (or 204 No Content if none).
- **Created:** October 7, 2025  
- **Last Updated:** October 7, 2025

---

### Running UATs
To run only these acceptance tests:
```bash
pytest -m uat -q
