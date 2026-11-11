"""Health endpoint contract: monitors probe it with HEAD as well as GET."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_get(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_head(client: TestClient) -> None:
    response = client.head("/health")
    assert response.status_code == 200
    assert response.content == b""
