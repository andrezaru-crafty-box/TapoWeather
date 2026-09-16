"""Settings, loaded from the environment.

Nothing secret is ever written in source. Values come from real environment
variables, or from a .env file sitting next to the repo which git is told to
ignore. If you clone this and run it, you supply your own.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"
PRESETS_FILE = REPO_ROOT / "presets.json"
LOCAL_PRESETS_FILE = REPO_ROOT / "presets.local.json"

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
REV_URL = "https://nominatim.openstreetmap.org/reverse"
WX_URL = "https://api.open-meteo.com/v1/forecast"

DEFAULT_PRESETS = [
    {"label": "Valletta, Malta", "lat": 35.8989, "lon": 14.5146},
    {"label": "Reykjavik, Iceland", "lat": 64.1466, "lon": -21.9426},
    {"label": "London, UK", "lat": 51.5072, "lon": -0.1276},
    {"label": "Singapore", "lat": 1.3521, "lon": 103.8198},
    {"label": "Tromso, Norway", "lat": 69.6492, "lon": 18.9553},
]


def load_env_file(path: Path = ENV_FILE) -> None:
    """Read KEY=value lines into the environment.

    Real environment variables win, so an exported password beats a stale line
    in the file. Deliberately tiny: no dependency, and no surprises about what
    it does with your secrets.
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, sep, value = line.partition("=")
        if not sep:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


@dataclass
class Settings:
    username: str = ""
    password: str = ""
    ips: list = field(default_factory=list)
    host: str = "0.0.0.0"
    port: int = 8765
    refresh_seconds: int = 600
    user_agent: str = "tapo-weather-lamp (personal home lighting project)"

    @classmethod
    def from_env(cls) -> "Settings":
        load_env_file()
        return cls(
            username=os.environ.get("TAPO_USERNAME", "").strip(),
            password=os.environ.get("TAPO_PASSWORD", ""),
            ips=[ip.strip() for ip in os.environ.get("TAPO_IPS", "").split(",") if ip.strip()],
            host=os.environ.get("LAMP_HOST", "0.0.0.0").strip() or "0.0.0.0",
            port=_int("LAMP_PORT", 8765),
            refresh_seconds=_int("LAMP_REFRESH_SECONDS", 600),
            user_agent=os.environ.get(
                "LAMP_USER_AGENT",
                "tapo-weather-lamp (personal home lighting project)",
            ),
        )

    def __repr__(self) -> str:
        """Never let a password reach a log line or a traceback."""
        shown = "set" if self.password else "unset"
        return (
            f"Settings(username={self.username!r}, password=<{shown}>, "
            f"ips={len(self.ips)} configured, host={self.host!r}, port={self.port})"
        )


def load_presets() -> list:
    """Your own list of places, if you keep one.

    presets.local.json is gitignored, so a list of the towns you actually care
    about stays on your machine rather than in your commit history.
    """
    for path in (LOCAL_PRESETS_FILE, PRESETS_FILE):
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list) and data:
                    return data
            except (json.JSONDecodeError, OSError):
                print(f"Could not read {path.name}, using the built-in presets.")
    return DEFAULT_PRESETS
