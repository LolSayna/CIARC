"""
Melvonaut
:author: Jonathan Decker
"""

# Load settings first to ensure the overrides are available
from melvonaut.settings import settings

import asyncio
import concurrent.futures
import io
import os
import re
import signal
import uvloop

from typing import Optional, AsyncIterable
from datetime import datetime, timezone

import aiohttp
import click

import aiodebug.log_slow_callbacks  # type: ignore
from PIL import Image
from aiofile import async_open
from loguru import logger

from melvonaut.mel_telemetry import MelTelemetry
from melvonaut.state_planer import state_planner
from melvonaut import api, utils
import shared.constants as con
from shared.models import Timer, Event, MelvinImage, CameraAngle

if settings.TRACING:
    import tracemalloc

    tracemalloc.start(5)


##### Global Variables #####
current_telemetry = None
aiodebug.log_slow_callbacks.enable(0.05)

# create a unique id each time melvonauts start, to allow better image sorting


# tracemalloc.start()


async def get_observations() -> None:
    """Async get observations from the Melvin API and update the state planner

    This function establishes a session with the API and retrieves observation data.
    If the response is successful, it updates the telemetry state.
    If any errors occur, they are logged accordingly.

    Returns:
        None

    """
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(con.OBSERVATION_ENDPOINT) as response:
                if response.status == 200:
                    json_response = await response.json()
                    # logger.debug("Received observations")
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
    """Runs the observation fetching function in a loop.

    This function repeatedly fetches observations based on a specified refresh rate,
    adjusting for simulation speed.

    Returns:
        None
    """
    await get_observations()
    while True:
        # logger.debug("Submitted observations request")
        observe_task = Timer(
            timeout=settings.OBSERVATION_REFRESH_RATE
            / state_planner.get_simulation_speed(),
            callback=get_observations,
        ).get_task()
        await asyncio.gather(observe_task)


# currently not in use
async def get_announcements() -> None:
    """Fetches real-time announcements from the Melvin API.

    This function opens a session with the announcements API endpoint,
    reads and logs any received messages.

    Returns:
        None
    """
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
    """Fetches announcements asynchronously with event-stream handling.

    This function continuously listens for new announcements from the API and processes them.
    If announcements are received, they are logged and stored.

    Args:
        last_id (Optional[str]): The ID of the last processed event to resume from, if applicable.

    Returns:
        Optional[str]: The ID of the last received announcement, or None if an error occurs.
    """
    content_line_regex = re.compile(r"^\[(\d+)]\s*(.*)$")

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
                    # logger.error(response.content)
                    # async for line in response.content:
                    #    logger.error(line)
                    async for line in response.content:
                        line_decoded = line.decode("utf-8")
                        # logger.warning(f"Received announcement {line}")
                        # logger.warning(f"Location is: {state_planner.calc_current_location()}")
                        # logger.warning(f"Received announcement with content:{line_decoded}")
                        line_filtered = line_decoded.replace("data:", "").strip()

                        match = content_line_regex.search(line_filtered)
                        if match:
                            line_id = int(match.group(1))
                            line_content = str(match.group(2))
                            timestamp = datetime.now(timezone.utc)
                            current_x, current_y = state_planner.calc_current_location()

                            current_event = Event(
                                event=line_content,
                                id=line_id,
                                timestamp=timestamp,
                                current_x=current_x,
                                current_y=current_y,
                            )

                            logger.warning(
                                f"Received announcement: {current_event.model_dump()}"
                            )
                            await current_event.to_csv()
                            state_planner.recent_events.append(current_event)
                            last_id = str(current_event.id)
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
    """Continuously fetches announcements from the API.

    This function runs in an infinite loop, restarting the subscription when needed.

    Returns:
        None
    """
    logger.warning("Started announcements subscription")
    while True:
        await asyncio.gather(get_announcements2())
        logger.warning("Restarted announcements subscription")


# not in use, can be removed
async def read_images() -> AsyncIterable[MelvinImage]:
    """Reads image files asynchronously from a designated directory.

    This function iterates over stored images, extracts metadata from filenames, and
    yields `MelvinImage` objects.

    Yields:
        MelvinImage: An image object containing extracted metadata.
    """
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
    """Log all receives images.

    Returns:
        None
    """
    async for image in read_images():
        logger.debug(f"Received image: {image}")


def cancel_tasks() -> None:
    """Cancels all tasks and event loop.

    Returns:
        None
    """
    for task in asyncio.all_tasks():
        task.cancel()
    loop = asyncio.get_running_loop()
    loop.stop()


def start_event_loop() -> None:
    """Initializes and starts the asynchronous event loop.

    This function sets up signal handlers, registers tasks for fetching observations,
    announcements, and API interactions, and starts the event loop.

    Returns:
        None
    """
    loop = uvloop.new_event_loop()

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
    utils.setup_logging()
    logger.info("Starting Melvonaut...")

    start_event_loop()


if __name__ == "__main__":
    main(prog_name="Melvonaut")  # pragma: no cover
