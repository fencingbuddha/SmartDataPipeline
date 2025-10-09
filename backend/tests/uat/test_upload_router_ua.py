"""
Title: Upload router handles success and common errors (UAT)
User Story: As a user, when I upload a CSV via the upload API, I receive a success response; if I make common mistakes (missing file or wrong field), I receive clear validation errors.
"""
from io import BytesIO
from datetime import date

import pytest
from fastapi.testclient import TestClient
from app.main import app

pytestmark = pytest.mark.uat
client = TestClient(app)


def test_upload_success_minimal_csv():
    today = date.today().isoformat()
    csv = f"timestamp,value,metric,source\n{today},1,events_total,uat-upload\n".encode()
    files = {"file": ("data.csv", BytesIO(csv), "text/csv")}
    r = client.post("/api/upload", params={"source_name": "uat-upload"}, files=files)
    assert r.status_code in (200, 201), r.text
    body = r.json()
    assert isinstance(body, dict) and body.get("ok") is True


def test_upload_missing_file_field_returns_422_or_400():
    # No 'file' part provided
    r = client.post("/api/upload", params={"source_name": "uat-upload-missing"})
    assert r.status_code in (400, 422), r.text


def test_upload_wrong_form_field_returns_400_422():
    # Wrong multipart field name -> should be rejected by validation or handler
    today = date.today().isoformat()
    csv = f"timestamp,value,metric,source\n{today},1,events_total,uat-upload-bad\n".encode()
    wrong = {"not_file": ("data.csv", BytesIO(csv), "text/csv")}
    r = client.post("/api/upload", params={"source_name": "uat-upload-bad"}, files=wrong)
    assert r.status_code in (400, 422), r.text
