"""Talking to Open-Meteo and to Nominatim.

Neither needs an API key. Nominatim does ask that you identify your app and
keep it under a call a second, which is why the user agent is configurable.
"""

from __future__ import annotations

import httpx

from .config import GEO_URL, REV_URL, WX_URL

CURRENT_FIELDS = "temperature_2m,weather_code,wind_speed_10m,cloud_cover,is_day"

# the fields Nominatim might use for the nearest named thing, best first
PLACE_KEYS = ("city", "town", "village", "municipality", "hamlet",
              "suburb", "county", "state", "region")


async def fetch_weather(http: httpx.AsyncClient, lat: float, lon: float) -> dict:
    r = await http.get(
        WX_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": CURRENT_FIELDS,
            "forecast_days": 1,
            "timezone": "auto",
        },
    )
    r.raise_for_status()
    return r.json()


async def search_places(http: httpx.AsyncClient, query: str) -> list:
    """Name -> a handful of candidate places."""
    r = await http.get(GEO_URL, params={"name": query, "count": 8, "language": "en"})
    results = r.json().get("results", []) or []
    return [
        {
            "name": p["name"],
            "country": ", ".join(b for b in (p.get("admin1"), p.get("country")) if b),
            "label": ", ".join(b for b in (p["name"], p.get("country")) if b),
            "lat": p["latitude"],
            "lon": p["longitude"],
        }
        for p in results
    ]


def format_coords(lat: float, lon: float) -> str:
    return (
        f"{abs(lat):.2f}\u00b0{'N' if lat >= 0 else 'S'} "
        f"{abs(lon):.2f}\u00b0{'E' if lon >= 0 else 'W'}"
    )


async def nearest_place(http: httpx.AsyncClient, lat: float, lon: float,
                        user_agent: str) -> dict:
    """A point on the map -> the nearest named town.

    Falls back to the bare coordinates, which is what happens out at sea. The
    weather there is just as real.
    """
    lat = max(-90.0, min(90.0, float(lat)))
    lon = (float(lon) + 540) % 360 - 180        # unwrap repeated worlds
    coords = format_coords(lat, lon)
    try:
        r = await http.get(
            REV_URL,
            params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 10},
            headers={"User-Agent": user_agent, "Accept-Language": "en"},
            timeout=8,
        )
        address = r.json().get("address") or {}
    except Exception:
        address = {}

    town = next((address[k] for k in PLACE_KEYS if address.get(k)), None)
    if not town:
        return {"label": coords, "lat": lat, "lon": lon, "snapped": False}
    return {
        "label": ", ".join(b for b in (town, address.get("country")) if b),
        "lat": lat,
        "lon": lon,
        "snapped": True,
    }


def classify(code: int) -> tuple:
    """WMO weather code -> (human label, effect name)."""
    if code == 0:
        return ("Clear sky", "clear")
    if code in (1, 2):
        return ("Partly cloudy", "partly_cloudy")
    if code == 3:
        return ("Overcast", "overcast")
    if code in (45, 48):
        return ("Fog", "fog")
    if code in (51, 53, 55, 56, 57):
        return ("Drizzle", "drizzle")
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return ("Rain", "rain")
    if code in (71, 73, 75, 77, 85, 86):
        return ("Snow", "snow")
    if code in (95, 96, 99):
        return ("Thunderstorm", "storm")
    return ("Overcast", "overcast")
