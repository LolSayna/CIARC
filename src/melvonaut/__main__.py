"""
Melvonaut
:author: Jonathan Decker
"""

import asyncio
import concurrent.futures
import io
import os
import re
import signal
import sys
from typing import Optional, AsyncIterable
from datetime import datetime, timezone

import aiohttp
import click

import aiodebug.log_slow_callbacks  # type: ignore
from PIL import Image
from aiofile import async_open

from loguru import logger
from melvonaut.mel_telemetry import MelTelemetry
from melvonaut.state_planer import StatePlanner
from melvonaut import api
import shared.constants as con
import melvonaut.settings as settings
from shared.models import Timer, Event, MelvinImage, CameraAngle
from melvonaut.loop_config import loop

if settings.TRACING:
    import tracemalloc

    tracemalloc.start(5)

##### LOGGING #####
logger.remove()
logger.add(sink=sys.stdout, level="DEBUG", backtrace=True, diagnose=True)
logger.add(
    sink=con.MEL_LOG_LOCATION,
    rotation="00:00",
    level="DEBUG",
    backtrace=True,
    diagnose=True,
)

##### Global Variables #####
current_telemetry = None
aiodebug.log_slow_callbacks.enable(0.05)

# create a unique id each time melvonauts start, to allow better image sorting


# tracemalloc.start()

state_planner = StatePlanner()


async def get_observations() -> None:
    """Async get observations from the Melvin API and update the state planner

    Returns:
        None

    """
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(con.OBSERVATION_ENDPOINT) as response:
                if response.status == 200:
                    json_response = await response.json()
                    logger.debug("Received observations")
                    # pprint(json_response, indent=4, sort_dicts=True)
                    await state_planner.update_telemetry(MelTelemetry(**json_response))
                else:
                    logger.warning(f"Failed to get observations: {response.status}")
        except aiohttp.client_exceptions.ConnectionTimeoutError:
            logger.warning("Observations endpoint timeouted.")
        except asyncio.TimeoutError:
            logger.warning("ASyncio TimeoutError occured.")
        except aiohttp.client_exceptions.ClientOSError:
            logger.warning("Client_exceptions.ClienOSError occured.")


async def run_get_observations() -> None:
    await get_observations()
    while True:
        logger.debug("Submitted observations request")
        observe_task = Timer(
            timeout=settings.OBSERVATION_REFRESH_RATE
            / state_planner.get_simulation_speed(),
            callback=get_observations,
        ).get_task()
        await asyncio.gather(observe_task)


# currently not in use
async def get_announcements() -> None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                con.ANNOUNCEMENTS_ENDPOINT, headers={"Accept": "text/event-stream"}
            ) as response:
                if response.status == 200:
                    async for line in response.content:
                        clean_line = line.decode("utf-8").strip().replace("data:", "")
                        logger.error(f"Received announcement: {clean_line}")
                else:
                    logger.error(f"Failed to get announcements: {response.status}")
    except TimeoutError:
        # could add async sleep here
        logger.error("Announcements subscription timed out")


async def get_announcements2(last_id: Optional[str] = None) -> Optional[str]:
    headers = {"Accept": "text/event-stream", "Cache-Control": "no-cache"}
    if last_id:
        headers["Last-Event-ID"] = last_id

    timeout = aiohttp.ClientTimeout(
        total=None, connect=None, sock_connect=None, sock_read=None
    )

    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.get(
                con.ANNOUNCEMENTS_ENDPOINT, headers=headers
            ) as response:
                if response.status not in [200, 301, 307]:
                    logger.error(f"Failed to get announcements: {response.status}")
                    await session.close()
                    return None
                else:
                    lines = []
                    async for line in response.content:
                        line = line.decode("utf-8")
                        # logger.warning(f"Received announcement {line}")
                        # logger.warning(f"Location is: {state_planner.calc_current_location()}")

                        logger.warning(f"Received announcement with content:{line}")
                        line = line.replace("data:", "")
                        if line in {"\n", "\r\n", " \r\n", "\r"}:
                            if not lines:
                                continue
                            if lines[0] == ":ok\n":
                                lines = []
                                continue
                            current_event = Event()
                            current_event.timestamp = datetime.now(timezone.utc)
                            current_event.current_x, current_event.current_y = (
                                state_planner.calc_current_location()
                            )
                            current_event.parse("".join(lines))
                            logger.warning(
                                f"Received announcement: {current_event.model_dump()}"
                            )
                            await current_event.to_csv()
                            state_planner.recent_events.append(current_event)
                            last_id = current_event.id
                            lines = []
                        else:
                            logger.debug(f"Appending event line: {line}/{repr(line)}")
                            lines.append(line)
        except TimeoutError:
            logger.error("Announcements subscription timed out")
        finally:
            if response and not response.closed:
                response.close()
            if not session.closed:
                await session.close()
            return last_id


# Irgendwie restartet der sich alle 5 sekunden, und glaube überlastet die API
async def run_get_announcements() -> None:
    logger.warning("Started announcements subscription")
    while True:
        await asyncio.gather(get_announcements2())
        logger.warning("Restarted announcements subscription")


# not in use, can be removed
async def read_images() -> AsyncIterable[MelvinImage]:
    if not os.path.exists(con.IMAGE_PATH):
        logger.warning(f"{con.IMAGE_PATH} does not exist.")
        return

    pattern = r"image_melvonaut_angle_(\w+)_x_(\d+\.\d+)_y_(\d+\.\d+)_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.png"

    for filename in os.listdir(con.IMAGE_PATH):
        if filename.endswith(".png"):
            image_path = os.path.join(con.IMAGE_PATH, filename)
            try:
                async with async_open(image_path, "rb") as afp:
                    data = await afp.read()
                    image = Image.open(io.BytesIO(data))
            except FileNotFoundError as e:
                logger.warning(f"{image_path} does not exist.")
                logger.debug(e)
                continue
            except IOError as e:
                logger.warning(f"Failed to read {image_path}")
                logger.debug(e)
                continue
            except ValueError as e:
                logger.warning(f"Failed to parse {image_path}")
                logger.debug(e)
                continue
            match = re.match(pattern, filename)
            if match:
                angle = CameraAngle(match.group(1))
                cor_x = int(match.group(2))
                cor_y = int(match.group(3))
                time = datetime.strptime(match.group(4), "%Y-%m-%d_%H-%M-%S")
                yield MelvinImage(
                    image=image, angle=angle, cor_x=cor_x, cor_y=cor_y, time=time
                )
            else:
                logger.warning(f"Failed to parse {filename}.")


async def run_read_images() -> None:
    async for image in read_images():
        logger.debug(f"Received image: {image}")


def cancel_tasks() -> None:
    for task in asyncio.all_tasks():
        task.cancel()
    loop.stop()


def start_event_loop() -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, cancel_tasks)

    loop.set_default_executor(concurrent.futures.ThreadPoolExecutor(max_workers=1))

    loop.create_task(run_get_observations())
    loop.create_task(run_get_announcements())

    loop.create_task(api.run_api())

    # loop.create_task(run_read_images())

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
