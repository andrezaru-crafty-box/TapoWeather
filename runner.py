"""The loop.

Weather is re-fetched on a slow timer. The sun is recomputed every beat, which
is what makes dusk slide in rather than snap: nothing waits for the next
network call to notice the light has changed.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from .effects import EFFECTS, State
from .lights import Lights
from .sky import sky_at
from .solar import local_now, solar_elevation, sun_events
from .weather import classify, fetch_weather


async def runner(state: State, lights: Lights, http: httpx.AsyncClient,
                 refresh_seconds: int = 600):
    loop = asyncio.get_running_loop()
    last_fetch = -1e9
    while True:
        if state.place is None:
            await state.changed.wait()
            state.changed.clear()
            continue

        if state.changed.is_set() or loop.time() - last_fetch > refresh_seconds:
            state.changed.clear()
            place = state.place
            try:
                data = await fetch_weather(http, place["lat"], place["lon"])
            except Exception as e:
                print(f"weather fetch failed: {e}")
                await asyncio.sleep(15)
                continue
            current = data["current"]
            state.wx = current
            state.offset = data["utc_offset_seconds"]
            state.sunrise, state.sunset, state.daylight_note = sun_events(
                place["lat"], place["lon"], state.offset
            )
            state.label, state.effect = classify(current["weather_code"])
            last_fetch = loop.time()
            print(
                f"{place['label']}: {state.label}, {current['temperature_2m']}C, "
                f"wind {current['wind_speed_10m']} km/h, "
                f"cloud {current['cloud_cover']}%, "
                f"local {local_now(state.offset):%H:%M} -> {state.effect}"
            )

        # re-evaluated every beat, so dusk slides in on its own
        elevation = solar_elevation(
            state.place["lat"], state.place["lon"], datetime.now(timezone.utc)
        )
        state.sky = sky_at(elevation, (state.wx or {}).get("cloud_cover") or 0)
        lights.sky = state.sky

        try:
            await EFFECTS[state.effect](state, lights)
        except Exception as e:
            print(f"bulb command failed: {e}")
            await asyncio.sleep(5)
