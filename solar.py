"""Where the sun is, computed rather than fetched.

Low-precision solar position, good to about a hundredth of a degree, which is
far finer than anything a light bulb can show. Everything downstream keys off
elevation - the sun's height above the horizon in degrees - so nothing breaks
at a latitude where the sun refuses to rise or set.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

# -0.833 deg: the sun's upper limb clears the horizon while the centre of the
# disc is still below it, and the atmosphere bends the light a little further.
HORIZON = -0.833


def _sun_coords(when_utc: datetime) -> tuple:
    """Declination and right ascension of the sun, plus Greenwich sidereal time."""
    jd = when_utc.timestamp() / 86400.0 + 2440587.5
    n = jd - 2451545.0                                        # days from J2000
    mean_long = math.radians((280.460 + 0.9856474 * n) % 360)
    anomaly = math.radians((357.528 + 0.9856003 * n) % 360)
    ecliptic = (
        mean_long
        + math.radians(1.915) * math.sin(anomaly)
        + math.radians(0.020) * math.sin(2 * anomaly)
    )
    obliquity = math.radians(23.439 - 0.0000004 * n)
    dec = math.asin(math.sin(obliquity) * math.sin(ecliptic))
    ra = math.atan2(math.cos(obliquity) * math.sin(ecliptic), math.cos(ecliptic))
    gmst_deg = (280.46061837 + 360.98564736629 * n) % 360
    return dec, ra, gmst_deg


def solar_elevation(lat: float, lon: float, when_utc: datetime) -> float:
    """Degrees above the horizon. Negative means the sun has set."""
    dec, ra, gmst_deg = _sun_coords(when_utc)
    hour_angle = math.radians((gmst_deg + lon) % 360) - ra
    phi = math.radians(lat)
    sin_alt = (
        math.sin(phi) * math.sin(dec)
        + math.cos(phi) * math.cos(dec) * math.cos(hour_angle)
    )
    return math.degrees(math.asin(max(-1.0, min(1.0, sin_alt))))


def subsolar_point(when_utc: datetime) -> tuple:
    """The one spot on Earth with the sun directly overhead."""
    dec, ra, gmst_deg = _sun_coords(when_utc)
    lon = (math.degrees(ra) - gmst_deg + 540) % 360 - 180
    return math.degrees(dec), lon


def to_utc(local_naive: datetime, offset_seconds: int) -> datetime:
    return local_naive.replace(tzinfo=timezone.utc) - timedelta(seconds=offset_seconds)


def local_now(offset_seconds: int) -> datetime:
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)).replace(tzinfo=None)


def sun_events(lat: float, lon: float, offset_seconds: int) -> tuple:
    """(sunrise, sunset, note) in naive local time, for the local day.

    Either time may be None. Above the Arctic and below the Antarctic circles a
    day can contain no crossing at all, in which case the note says what kind of
    day it is instead. This is why the sun is computed here rather than read off
    Open-Meteo's sunrise and sunset fields, which come back null at those
    latitudes.
    """
    midnight = local_now(offset_seconds).replace(hour=0, minute=0, second=0, microsecond=0)
    step = timedelta(minutes=4)
    rise = dusk = None
    prev = None

    for i in range(361):                      # a whole day, plus one step over
        t_local = midnight + step * i
        elev = solar_elevation(lat, lon, to_utc(t_local, offset_seconds)) - HORIZON
        if prev is not None:
            prev_elev, prev_local = prev
            if prev_elev < 0 <= elev and rise is None:
                rise = prev_local + step * (prev_elev / (prev_elev - elev))
            elif prev_elev >= 0 > elev and dusk is None:
                dusk = prev_local + step * (prev_elev / (prev_elev - elev))
        prev = (elev, t_local)

    if rise is None and dusk is None:
        noon = solar_elevation(
            lat, lon, to_utc(midnight + timedelta(hours=12), offset_seconds)
        )
        return None, None, ("Midnight sun" if noon > HORIZON else "Polar night")
    return rise, dusk, None


def terminator(when_utc: datetime | None = None) -> dict:
    """The line between day and night, plus which pole lies in darkness."""
    when_utc = when_utc or datetime.now(timezone.utc)
    dec, sub_lon = subsolar_point(when_utc)
    tan_dec = math.tan(math.radians(dec))
    if abs(tan_dec) < 1e-6:                  # equinox: the line runs pole to pole
        tan_dec = math.copysign(1e-6, tan_dec or 1.0)
    points = [
        [
            math.degrees(math.atan(-math.cos(math.radians(i - sub_lon)) / tan_dec)),
            float(i),
        ]
        for i in range(-180, 181, 2)
    ]
    return {"points": points, "pole": 90.0 if dec < 0 else -90.0}
