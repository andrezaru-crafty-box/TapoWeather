"""Entry point: python -m tapo_weather"""

from __future__ import annotations

import asyncio

import httpx
import uvicorn

from .config import Settings
from .effects import State
from .lights import Lights, connect_bulbs, settle
from .runner import runner
from .server import build_app


async def main():
    settings = Settings.from_env()
    state = State()

    async with httpx.AsyncClient(timeout=15) as http:
        bulbs = await connect_bulbs(settings)
        state.bulb_count = len(bulbs)
        lights = Lights(bulbs)
        if bulbs:
            await lights.on()

        app = build_app(state, http, settings)
        config = uvicorn.Config(
            app, host=settings.host, port=settings.port, log_level="warning"
        )
        server = uvicorn.Server(config)

        where = "localhost" if settings.host in ("0.0.0.0", "127.0.0.1") else settings.host
        print(f"\nPanel: http://{where}:{settings.port}")
        if settings.host == "0.0.0.0":
            print("       (same port on this machine's LAN address, from your phone)")
        print()

        try:
            await asyncio.gather(server.serve(), runner(state, lights, http,
                                                        settings.refresh_seconds))
        finally:
            await settle(lights)


def run():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    run()
