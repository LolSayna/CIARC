import asyncio
from aiohttp import web, ClientSession

from melvonaut.settings import settings
from shared import constants as con
from melvonaut.api import setup_routes, compression_middleware, catcher_middleware
from loguru import logger
from melvonaut.mel_telemetry import MelTelemetry
from shared.models import CameraAngle, State, Event
from datetime import datetime
from PIL import Image

async def main():
    async with ClientSession() as session:
        async with session.get("/api/health") as resp:
            print(resp.status)
            print(await resp.text())


asyncio.run(main())