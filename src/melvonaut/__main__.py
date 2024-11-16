"""Command-line interface."""

import asyncio
import datetime
import json
import signal
import sys
from collections.abc import Callable
from enum import StrEnum
from pprint import pprint
from typing import Any, Awaitable, Optional

import aiohttp
import click
from aiofile import async_open
from loguru import logger
import uvloop
from pydantic import BaseModel, ConfigDict

import melvonaut.constants as con

logger.remove()
logger.add(sink=sys.stderr, level="DEBUG", backtrace=True, diagnose=True)
logger.add(
    sink=con.LOG_LOCATION,
    rotation="00:00",
    level="DEBUG",
    backtrace=True,
    diagnose=True,
)

loop = uvloop.new_event_loop()


class State(StrEnum):
    Deployment = "deployment"
    Acquisition = "acquisition"
    Charge = "charge"
    Safe = "safe"
    Communication = "communication"
    Transition = "transition"
    Unknown = "none"


class Angle(StrEnum):
    Wide = "wide"
    Narrow = "narrow"
    Normal = "normal"
    Unknown = "unknown"


class AreaCovered(BaseModel):
    narrow: float
    normal: float
    wide: float

class DataVolume(BaseModel):
    data_volume_received: int
    data_volume_sent: int


class Telemetry(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    active_time: float
    angle: Angle
    area_covered: AreaCovered
    battery: float
    data_volume: DataVolume
    distance_covered: float
    fuel: float
    height_y: float
    images_taken: int
    max_battery: float
    objectives_done: int
    objectives_points: int
    simulation_speed: int
    state: State
    timestamp: datetime.datetime
    vx: float
    vy: float
    width_x: float

    async def store_observation(self) -> None:
        logger.info("Storing observation")
        try:
            async with async_open(con.TELEMETRY_LOCATION, "r") as afp:
                raw_telemetry = await afp.read()
                dict_telemetry = json.loads(raw_telemetry)
        except FileNotFoundError:
            logger.debug(f"{con.TELEMETRY_LOCATION} does not exist.")
            dict_telemetry = {}

        timestamp = self.timestamp.isoformat()
        new_telemetry_entry = self.model_dump(exclude={"timestamp"})
        dict_telemetry[timestamp] = new_telemetry_entry
        json_telemetry = json.dumps(dict_telemetry, indent=4, sort_keys=True)

        async with async_open(con.TELEMETRY_LOCATION, "w") as afp:
            logger.debug(f"Writing to {con.TELEMETRY_LOCATION}")
            await afp.write(str(json_telemetry))
        logger.debug("Observation stored")

    def model_post_init(self, __context__: Any) -> None:
        loop.create_task(self.store_observation())


current_telemetry = None


class Timer(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    _timeout: int
    _callback: Callable[[], Awaitable[Any]]
    _task: asyncio.Task[None]

    def __init__(self, timeout: int, callback: Callable[[], Awaitable[Any]]):
        super().__init__()
        self._timeout = timeout
        self._callback = callback
        self._task = asyncio.create_task(self._job())

    async def _job(self) -> None:
        await asyncio.sleep(self._timeout)
        await self._callback()

    def cancel(self) -> None:
        self._task.cancel()

    def get_task(self) -> asyncio.Task[None]:
        return self._task


class StatePlanner(BaseModel):
    current_telemetry: Optional[Telemetry] = None
    previous_telemetry: Optional[Telemetry] = None

    def get_current_state(self) -> State:
        return self.current_telemetry.state

    def get_previous_state(self) -> State:
        return self.previous_telemetry.state

    def update_telemetry(self, new_telemetry: Telemetry) -> None:
        self.previous_telemetry = self.current_telemetry
        self.current_telemetry = new_telemetry

        if self.previous_telemetry is not None:
            pass



state_planner = StatePlanner()


async def get_observations() -> None:
    async with aiohttp.ClientSession() as session:
        async with session.get(con.OBSERVATION_ENDPOINT) as response:
            if response.status == 200:
                json_response = await response.json()
                logger.info("Received observations")
                pprint(json_response, indent=4, sort_dicts=True)
                state_planner.update_telemetry(Telemetry(**json_response))
            else:
                logger.warning(f"Failed to get observations: {response.status}")


async def run_get_observations() -> None:
    await get_observations()
    while True:
        logger.info("Submitted observations request")
        observe_task = Timer(timeout=con.OBSERVATION_REFRESH_RATE, callback=get_observations).get_task()
        await asyncio.gather(observe_task)


async def get_announcements() -> None:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            con.ANNOUNCEMENTS_ENDPOINT, headers={"Accept": "text/event-stream"}
        ) as response:
            if response.status == 200:
                async for line in response.content:
                    clean_line = line.decode("utf-8").strip()
                    logger.info(f"Received announcement: {clean_line}")
            else:
                logger.warning(f"Failed to get announcements: {response.status}")


async def run_get_announcements() -> None:
    logger.info("Started announcements subscription")
    while True:
        await asyncio.gather(get_announcements())
        logger.info("Restarted announcements subscription")


def cancel_tasks() -> None:
    for task in asyncio.all_tasks():
        task.cancel()
    loop = asyncio.get_event_loop()
    loop.stop()


def start_event_loop() -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, cancel_tasks)

    loop.create_task(run_get_observations())
    loop.create_task(run_get_announcements())

    loop.run_forever()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.remove_signal_handler(sig)

    logger.info("Shutting down Melvonaut...")


@click.command()
@click.version_option()
def main() -> None:
    """Melvonaut."""
    logger.info("Starting Melvonaut...")

    start_event_loop()


if __name__ == "__main__":
    main(prog_name="Melvonaut")  # pragma: no cover
