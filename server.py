"""The web panel and its endpoints."""

from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings, load_presets
from .effects import LOOKS, State
from .solar import local_now, terminator
from .weather import nearest_place, search_places

WEB_DIR = Path(__file__).resolve().parent / "web"


def build_app(state: State, http: httpx.AsyncClient, settings: Settings) -> FastAPI:
    app = FastAPI(title="Weather lamp", docs_url=None, redoc_url=None)
    presets = load_presets()

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/")
    async def index():
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/api/presets")
    async def api_presets():
        return presets

    @app.get("/api/search")
    async def api_search(q: str):
        return await search_places(http, q)

    @app.post("/api/reverse")
    async def api_reverse(point: dict):
        return await nearest_place(
            http, point["lat"], point["lon"], settings.user_agent
        )

    @app.get("/api/terminator")
    async def api_terminator():
        return terminator()

    @app.post("/api/place")
    async def api_place(place: dict):
        state.set_place(
            {
                "label": str(place["label"])[:120],
                "lat": max(-90.0, min(90.0, float(place["lat"]))),
                "lon": (float(place["lon"]) + 540) % 360 - 180,
            }
        )
        return {"ok": True}

    @app.get("/api/status")
    async def api_status():
        if not state.effect or not state.wx:
            return JSONResponse({"place": None, "bulbs": state.bulb_count})

        color, anim = LOOKS[state.effect]
        sky = state.sky
        here = f"sun {sky.elevation:+.1f}\u00b0 now"

        if state.daylight_note:
            sunline = f"{state.daylight_note} \u00b7 {here}"
        elif state.sunrise and state.sunset and state.sunset < state.sunrise:
            # far enough north or south that the local day opens with the sun
            # already up, so it sets before it rises again
            sunline = (
                f"sets {state.sunset:%H:%M}, rises {state.sunrise:%H:%M} \u00b7 {here}"
            )
        else:
            rise = f"{state.sunrise:%H:%M}" if state.sunrise else "--:--"
            sets = f"{state.sunset:%H:%M}" if state.sunset else "--:--"
            sunline = f"{rise} to {sets} \u00b7 {here}"

        return JSONResponse(
            {
                "place": state.place["label"],
                "lat": state.place["lat"],
                "lon": state.place["lon"],
                "condition": state.label,
                "effect": state.effect,
                "temperature": state.wx["temperature_2m"],
                "wind": state.wx["wind_speed_10m"],
                "cloud": state.wx.get("cloud_cover"),
                "time": f"{local_now(state.offset):%H:%M}",
                "phase": sky.name,
                "elevation": round(sky.elevation, 2),
                "sunline": sunline,
                "color": color,
                "anim": anim,
                "dim": round(sky.bri_scale, 3),
                "sky": sky.hex,
                "sky_alpha": round(sky.veil, 3),
                "bulbs": state.bulb_count,
            }
        )

    return app
