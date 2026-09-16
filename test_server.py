"""Endpoint tests. No network: the weather and geocoding calls are stubbed."""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from tapo_weather import runner as runner_module

from tapo_weather.config import Settings
from tapo_weather.effects import State
from tapo_weather.lights import Lights
from tapo_weather.server import build_app

SAMPLE_CURRENT = {
    "temperature_2m": 12.4,
    "weather_code": 61,
    "wind_speed_10m": 18.0,
    "cloud_cover": 74,
    "is_day": 1,
}


@pytest.fixture
def client():
    state = State()
    http = httpx.AsyncClient()
    app = build_app(state, http, Settings())
    with TestClient(app) as c:
        yield c, state


def test_index_serves_the_panel(client):
    c, _ = client
    r = c.get("/")
    assert r.status_code == 200
    assert "Weather lamp" in r.text
    assert "/static/panel.js" in r.text


def test_static_assets_are_served(client):
    c, _ = client
    assert c.get("/static/panel.css").status_code == 200
    assert c.get("/static/panel.js").status_code == 200


def test_presets_are_a_list_of_places(client):
    c, _ = client
    presets = c.get("/api/presets").json()
    assert presets and all({"label", "lat", "lon"} <= set(p) for p in presets)


def test_status_before_a_place_is_chosen(client):
    c, _ = client
    assert c.get("/api/status").json() == {"place": None, "bulbs": 0}


def test_terminator_shape(client):
    c, _ = client
    t = c.get("/api/terminator").json()
    assert len(t["points"]) == 181
    assert t["pole"] in (90.0, -90.0)


def test_place_is_clamped_and_wrapped(client):
    c, state = client
    c.post("/api/place", json={"label": "Somewhere", "lat": 200.0, "lon": 359.87})
    assert state.place["lat"] == 90.0
    assert state.place["lon"] == pytest.approx(-0.13, abs=0.01)


def test_absurdly_long_labels_are_truncated(client):
    c, state = client
    c.post("/api/place", json={"label": "x" * 5000, "lat": 0, "lon": 0})
    assert len(state.place["label"]) == 120


def test_reverse_falls_back_to_coordinates_when_geocoding_fails(client, monkeypatch):
    """Clicking open ocean, or Nominatim being down, must not break the map."""
    c, _ = client

    async def no_service(*args, **kwargs):
        raise httpx.ConnectError("no network")

    from tapo_weather import weather as weather_module
    monkeypatch.setattr(weather_module.httpx.AsyncClient, "get", no_service)

    r = c.post("/api/reverse", json={"lat": -35.0, "lon": -25.0}).json()
    assert r["snapped"] is False
    assert "35.00" in r["label"] and "S" in r["label"]


def test_status_after_a_runner_pass(monkeypatch):
    """The full loop, with the weather stubbed, produces a complete panel payload."""

    async def fake_fetch(http, lat, lon):
        return {"current": dict(SAMPLE_CURRENT), "utc_offset_seconds": 3600}

    monkeypatch.setattr(runner_module, "fetch_weather", fake_fetch)

    async def go():
        state = State()
        lights = Lights([])
        async with httpx.AsyncClient() as http:
            app = build_app(state, http, Settings())
            with TestClient(app) as c:
                c.post("/api/place", json={"label": "Tromso", "lat": 69.6492, "lon": 18.9553})
                task = asyncio.create_task(runner_module.runner(state, lights, http))
                await asyncio.sleep(1.5)
                payload = c.get("/api/status").json()
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                return payload

    s = asyncio.run(go())
    assert s["condition"] == "Rain"
    assert s["effect"] == "rain"
    assert s["anim"] == "patter"
    assert s["cloud"] == 74
    assert s["sky"].startswith("#") and len(s["sky"]) == 7
    assert 0.0 <= s["sky_alpha"] <= 1.0
    assert 0.0 < s["dim"] <= 1.0
    assert "sun" in s["sunline"]
    assert -90 <= s["elevation"] <= 90
