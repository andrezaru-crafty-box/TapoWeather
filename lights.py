"""Driving the bulbs.

An empty bulb list is preview mode: every call becomes a no-op, so the whole
thing runs on a laptop with no hardware and no password.
"""

from __future__ import annotations

import asyncio
import getpass

from .config import Settings
from .sky import lerp_hue, sky_at


class Lights:
    """Fans every command out to all bulbs at once, applying the current sky.

    Effects that want bulbs out of step address them one at a time with
    hsb_at(). bulbs=[] means preview only.
    """

    def __init__(self, bulbs):
        self.bulbs = bulbs
        self.sky = sky_at(30.0)

    @property
    def count(self) -> int:
        # at least 1 so preview mode still ticks along at a sane pace
        return max(1, len(self.bulbs))

    def _hsb(self, hue, sat, bri) -> tuple:
        s = self.sky
        if s.hue_blend > 0:
            hue = lerp_hue(hue, s.hue_target, s.hue_blend)
        return (
            max(1, min(360, int(hue))),
            max(1, min(100, int(sat))),
            max(1, min(100, int(bri * s.bri_scale))),
        )

    async def on(self):
        await asyncio.gather(*(b.on() for b in self.bulbs))

    async def hsb(self, hue, sat, bri):
        h, s, b_ = self._hsb(hue, sat, bri)
        await asyncio.gather(
            *(b.set().hue_saturation(h, s).brightness(b_).send(b) for b in self.bulbs)
        )

    async def hsb_at(self, i, hue, sat, bri):
        """Drive a single bulb. Out of range (preview mode) is a no-op."""
        if i >= len(self.bulbs):
            return
        h, s, b_ = self._hsb(hue, sat, bri)
        bulb = self.bulbs[i]
        await bulb.set().hue_saturation(h, s).brightness(b_).send(bulb)

    async def kelvin(self, k, bri):
        s = self.sky
        k = max(2500, min(6500, int(k + s.kelvin_bias)))
        bri = max(1, min(100, int(bri * s.bri_scale)))
        await asyncio.gather(
            *(b.set().color_temperature(k).brightness(bri).send(b) for b in self.bulbs)
        )


async def connect_bulbs(settings: Settings) -> list:
    """Log in and reach the bulbs. Returns [] for preview mode.

    The password is read from the environment or typed at the prompt. It is
    never written to disk by this program and never printed.
    """
    if not settings.ips:
        print("No bulb addresses set (TAPO_IPS) - preview only.")
        return []

    user = settings.username
    if not user:
        print("No TAPO_USERNAME set - preview only.")
        return []

    password = settings.password
    if not password:
        print(f"Tapo password for {user}")
        print("(leave blank to run the panel in preview, without the bulbs)")
        password = getpass.getpass("Password: ").strip()
    if not password:
        print("No password - preview only.")
        return []

    from tapo import ApiClient  # imported here so preview mode needs no install

    client = ApiClient(user, password)
    # gathered with return_exceptions, so one sleeping bulb doesn't take the
    # others down with it
    results = await asyncio.gather(
        *(client.l530(ip) for ip in settings.ips), return_exceptions=True
    )
    bulbs = []
    for ip, res in zip(settings.ips, results):
        if isinstance(res, Exception):
            print(f"  {ip}: unreachable ({type(res).__name__})")
        else:
            print(f"  {ip}: connected")
            bulbs.append(res)
    if not bulbs:
        print("No bulbs reachable - check the addresses and your Tapo login.")
    return bulbs


async def settle(lights: Lights):
    """Leave the bulbs somewhere liveable on the way out."""
    if not lights.bulbs:
        return
    lights.sky = sky_at(30.0)          # no tint, so this lands where it says
    try:
        await asyncio.wait_for(lights.kelvin(3000, 60), 5)
        print("Bulbs returned to warm white.")
    except Exception:
        pass
