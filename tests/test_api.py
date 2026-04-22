"""Integration tests for the Flask API."""

from __future__ import annotations

import io
import json


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_json()
    assert body["service"] == "Network Interface Intelligence Platform"
    assert "docs" in body


def test_health_endpoint(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["service"] == "niip"


def test_swagger_ui_available(client):
    response = client.get("/api/v1/docs")
    # Either renders swagger or redirects to it
    assert response.status_code in (200, 308, 301)


def test_upload_csv_analysis(client, sample_csv_content):
    data = {
        "file": (io.BytesIO(sample_csv_content.encode("utf-8")), "sample.csv"),
    }
    response = client.post(
        "/api/v1/analysis/upload",
        data=data,
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["summary"]["total_interfaces"] == 3
    assert len(body["interfaces"]) == 3
    # Should be sorted critical → healthy
    assert body["interfaces"][0]["status"] in ("critical", "warning")


def test_upload_rejects_non_csv(client):
    data = {"file": (io.BytesIO(b"hello"), "evil.exe")}
    response = client.post(
        "/api/v1/analysis/upload",
        data=data,
        content_type="multipart/form-data",
    )
    assert response.status_code == 400


def test_upload_rejects_empty_file(client):
    data = {"file": (io.BytesIO(b""), "empty.csv")}
    response = client.post(
        "/api/v1/analysis/upload",
        data=data,
        content_type="multipart/form-data",
    )
    assert response.status_code == 400


def test_analyze_json_payload(client):
    payload = {
        "interfaces": [
            {
                "device_name": "rtr-01",
                "interface_name": "Gi0/1",
                "interface_description": "Test",
                "in_utilization_percent": 10.0,
                "out_utilization_percent": 12.0,
                "in_errors_1h": 0,
                "out_errors_1h": 0,
                "in_discards_1h": 0,
                "out_discards_1h": 0,
            },
            {
                "device_name": "rtr-01",
                "interface_name": "Gi0/2",
                "interface_description": "Congested",
                "in_utilization_percent": 92.0,
                "out_utilization_percent": 89.0,
                "in_errors_1h": 0,
                "out_errors_1h": 0,
                "in_discards_1h": 400,
                "out_discards_1h": 350,
            },
        ]
    }
    response = client.post(
        "/api/v1/analysis/analyze",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["summary"]["total_interfaces"] == 2
    # Congested interface should be critical
    statuses = {i["status"] for i in body["interfaces"]}
    assert "critical" in statuses or "warning" in statuses


def test_analyze_rejects_invalid_payload(client):
    response = client.post(
        "/api/v1/analysis/analyze",
        data=json.dumps({"interfaces": []}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_analyze_rejects_non_json(client):
    response = client.post(
        "/api/v1/analysis/analyze",
        data="not-json",
        content_type="application/json",
    )
    assert response.status_code == 400


def test_summary_endpoint(client, sample_csv_content):
    data = {"file": (io.BytesIO(sample_csv_content.encode("utf-8")), "sample.csv")}
    response = client.post(
        "/api/v1/analysis/summary",
        data=data,
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    body = response.get_json()
    assert "summary" in body
    assert "interfaces" not in body  # summary endpoint omits per-interface data


def test_unknown_endpoint_returns_404_json(client):
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404
    body = response.get_json()
    assert body["error"] == "NOT_FOUND"
