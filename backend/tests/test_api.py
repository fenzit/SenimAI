import pytest
from fastapi.testclient import TestClient
from app.core.config import settings
from app.main import app

settings.MOCK_MODE = True
client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "docs" in data


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_demo_cases_endpoint():
    response = client.get("/api/v1/demo-cases")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3


def test_analyze_empty_text():
    response = client.post("/api/v1/analyze", json={"text": ""})
    assert response.status_code == 422 or response.status_code == 400


def test_analyze_mock_mode():
    payload = {
        "text": "Первый человек высадился на Марсе в 1969 году.",
        "language": "ru",
        "max_claims": 5,
    }
    response = client.post("/api/v1/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "analysis_id" in data
    assert "summary" in data
    assert "claims" in data
    assert len(data["claims"]) > 0

    # Summary checks
    summary = data["summary"]
    assert "total_claims" in summary
    assert "verification_score" in summary
    assert 0.0 <= summary["verification_score"] <= 1.0

    # Claim checks
    claim = data["claims"][0]
    assert "id" in claim
    assert "text" in claim
    assert "verdict" in claim
    assert "confidence" in claim
    assert "explanation" in claim
    assert "sources" in claim


def test_export_markdown():
    payload = {
        "text": "Первый человек высадился на Марсе в 1969 году.",
        "language": "ru",
        "max_claims": 5,
    }
    analyze_resp = client.post("/api/v1/analyze", json=payload)
    assert analyze_resp.status_code == 200

    export_resp = client.post("/api/v1/export/markdown", json=analyze_resp.json())
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert "markdown" in export_data
    assert "# 🛡️ AI Trust Verification Report" in export_data["markdown"]

