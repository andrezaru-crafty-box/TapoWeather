"""What each kind of weather does to the light.

An effect runs for a beat of a few seconds and then returns, so the runner can
re-check the sun and the weather between beats. Effects never sleep on a bare
timer if they can help it: hold() wakes early when the place changes, so the
panel feels responsive even mid-thunderstorm.
"""

from __future__ import annotations

import asyncio
import math
import random

from .sky import sky_at

EFFECTS = {}

# effect -> (base colour for the panel lamp, css animation name)
LOOKS = {
    "clear": ("#FFE9B8", "steady"),
    "partly_cloudy": ("#FFD98A", "drift"),
    "overcast": ("#8896A6", "steady"),
    "fog": ("#B9C6CE", "drift"),
    "drizzle": ("#5C8FD6", "drift"),
    "rain": ("#2E6FD9", "patter"),
    "snow": ("#CFEAF5", "drift"),
    "storm": ("#3B3F8F", "strike"),
}


class State:
    """Everything the panel and the runner both need to see."""

    def __init__(self):
        self.place = None          # {"label", "lat", "lon"}
        self.wx = None             # Open-Meteo "current" block
        self.offset = 0            # seconds from UTC at the place
        self.sunrise = None
        self.sunset = None
        self.daylight_note = None  # "Midnight sun" / "Polar night" / None
        self.label = None          # "Rain"
        self.effect = None         # "rain"
        self.sky = sky_at(30.0)
        self.changed = asyncio.Event()
        self.bulb_count = 0

    def set_place(self, place: dict):
        self.place = place
        self.changed.set()


async def hold(state: State, seconds: float):
    """Sleep, but wake early if the place changes."""
    try:
        await asyncio.wait_for(state.changed.wait(), seconds)
    except asyncio.TimeoutError:
        pass


def effect(name):
    def deco(fn):
        EFFECTS[name] = fn
        return fn

    return deco


async def breathe(state, lights, hue, sat, lo, hi, step_s):
    for bri in list(range(lo, hi, 4)) + list(range(hi, lo, -4)):
        if state.changed.is_set():
            return
        await lights.hsb(hue, sat, bri)
        await asyncio.sleep(step_s)


async def breathe_apart(state, lights, hue, sat, lo, hi, period, beat=6.0):
    """Like breathe(), but every bulb gets its own phase and its own slightly
    different period, so they drift apart instead of locking together."""
    loop = asyncio.get_running_loop()
    end = loop.time() + beat
    mid, amp = (lo + hi) / 2, (hi - lo) / 2

    async def one(i):
        phase = random.uniform(0, math.tau)
        p = period * random.uniform(0.8, 1.2)   # detuned: they never re-sync
        while loop.time() < end and not state.changed.is_set():
            bri = mid + amp * math.sin(phase + loop.time() * math.tau / p)
            await lights.hsb_at(i, hue, sat, bri)
            await asyncio.sleep(0.12)

    await asyncio.gather(*(one(i) for i in range(lights.count)))


@effect("clear")
async def _clear(state, lights):
    # after dark the sky turns this into a dim blue; near the horizon, a low
    # warm glow - both of those come from the tint rather than from here
    if state.sky.night:
        await lights.hsb(230, 60, 40)
    else:
        await lights.kelvin(5000, 100)
    await hold(state, 8)


@effect("partly_cloudy")
async def _partly(state, lights):
    await lights.kelvin(4500, 90)      # sun
    await hold(state, random.uniform(3, 7))
    await lights.kelvin(4500, 45)      # cloud passing over
    await hold(state, random.uniform(3, 7))


@effect("overcast")
async def _overcast(state, lights):
    await lights.hsb(210, 12, 35)
    await hold(state, 8)


@effect("fog")
async def _fog(state, lights):
    await breathe(state, lights, 200, 8, 15, 30, 0.12)


@effect("drizzle")
async def _drizzle(state, lights):
    await breathe_apart(state, lights, 205, 65, 20, 45, period=2.6)


@effect("rain")
async def _rain(state, lights):
    """Each bulb gets its own droplet rhythm, so they never fall together."""
    loop = asyncio.get_running_loop()
    heaviness = min(1.0, (state.wx["wind_speed_10m"] or 0) / 40)  # windier = busier
    gap_hi = 1.6 - 0.9 * heaviness
    beat_end = loop.time() + 6.0

    async def stream(i):
        await asyncio.sleep(random.uniform(0, 0.9))   # stagger the starts
        while loop.time() < beat_end and not state.changed.is_set():
            await lights.hsb_at(i, 215, 80, random.randint(34, 46))
            await asyncio.sleep(random.uniform(0.35, gap_hi))
            await lights.hsb_at(i, 215, 80, random.randint(16, 24))   # droplet
            await asyncio.sleep(random.uniform(0.1, 0.24))

    await asyncio.gather(*(stream(i) for i in range(lights.count)))


@effect("snow")
async def _snow(state, lights):
    await breathe_apart(state, lights, 190, 15, 45, 85, period=5.0)


@effect("storm")
async def _storm(state, lights):
    await lights.hsb(240, 70, 15)
    await hold(state, random.uniform(2, 6))
    for _ in range(random.randint(1, 3)):   # lightning ignores the tint
        await lights.kelvin(6500, 100)
        await asyncio.sleep(0.06)
        await lights.hsb(240, 70, 8)
        await asyncio.sleep(random.uniform(0.05, 0.2))
    await lights.hsb(240, 70, 15)
    await asyncio.sleep(1)
