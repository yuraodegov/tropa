"""Overpass mirror fallback, tested with a fake transport (no network)."""
import asyncio

import httpx
import pytest

from app.places import PlacesUnavailable, fetch_places

OK_BODY = {"elements": [
    {"type": "node", "id": 1, "lat": 41.89, "lon": 12.49,
     "tags": {"name": "Colosseo", "tourism": "attraction"}},
]}


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_falls_back_to_next_mirror():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host)
        if request.url.host == "bad.example":
            return httpx.Response(502)
        return httpx.Response(200, json=OK_BODY)

    async def run():
        async with _client(handler) as c:
            return await fetch_places(c, 41.9, 12.5,
                                      urls=["https://bad.example/i", "https://good.example/i"])

    places = asyncio.run(run())
    assert calls == ["bad.example", "good.example"]
    assert places[0].name == "Colosseo"


def test_all_mirrors_down_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    async def run():
        async with _client(handler) as c:
            await fetch_places(c, 41.9, 12.5, urls=["https://a.example/i", "https://b.example/i"])

    with pytest.raises(PlacesUnavailable, match="HTTP 429"):
        asyncio.run(run())
