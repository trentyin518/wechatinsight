"""Qovia provider: upstream-busy detection, retry, and error mapping."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.core.errors import DataSourceBusy, DataSourceUnavailable
from app.providers.qovia import QoviaProvider


def _run(handler, *, max_retries: int = 0):
    async def _run_async():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = QoviaProvider(
                api_key="test-key",
                base_url="http://qovia.test",
                client=client,
                max_retries=max_retries,
                backoff=0.0,
            )
            return await provider.search_accounts("汽车之家")

    return asyncio.run(_run_async())


def test_upstream_busy_maps_to_datasource_busy():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503, json={"error": {"code": "upstream_busy", "message": "busy; not charged"}}
        )

    with pytest.raises(DataSourceBusy):
        _run(handler)


def test_generic_5xx_maps_to_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="<html>bad gateway</html>")

    with pytest.raises(DataSourceUnavailable):
        _run(handler)


def test_busy_retries_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, json={"error": {"code": "upstream_busy"}})
        return httpx.Response(
            200,
            json={
                "data": {
                    "items": [
                        {"mp_id": "abc", "name": "汽车之家", "description": "desc"},
                    ]
                }
            },
        )

    page = _run(handler, max_retries=2)
    assert calls["n"] == 2
    assert len(page.items) == 1
    assert page.items[0].name == "汽车之家"
