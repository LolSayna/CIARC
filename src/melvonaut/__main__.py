"""Command-line interface."""

import asyncio
import signal
import sys
from collections.abc import Callable
from pprint import pprint
from typing import Any, Awaitable

import aiohttp
import click
from loguru import logger
import uvloop
import enum

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


class State(enum.Enum):
    Deployment = "Deployment"
    Acquisition = "Acquisition"
    Charge = "Charge"
    Safe = "Safe"
    Comm = "Comm"
    Transition = "Transition"
    Unknown = "Unknown"


class Timer(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    timeout: int
    callback: Callable[[], Awaitable[Any]]
    task: asyncio.Task[None]

    def __init__(self, timeout: int, callback: Callable[[], Awaitable[Any]]) -> None:
        super().__init__()
        self.timeout = timeout
        self.callback = callback
        self.task = asyncio.create_task(self._job())

    async def _job(self) -> None:
        await asyncio.sleep(self.timeout)
        await self.callback()

    def cancel(self) -> None:
        self.task.cancel()


async def get_observations() -> None:
    async with aiohttp.ClientSession() as session:
        async with session.get(con.OBSERVATION_ENDPOINT) as response:
            if response.status == 200:
                json_response = await response.json()
                logger.info("Received observations")
                pprint(json_response, indent=4, sort_dicts=True)
            else:
                logger.warning(f"Failed to get observations: {response.status}")


async def run_get_observations() -> None:
    await get_observations()
    while True:
        logger.info("Submitted observations request")
        observe_task = Timer(10, get_observations).task
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
    loop = uvloop.new_event_loop()
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
