"""Command-line interface."""

import asyncio
import datetime
import io
import json
import os
import re
import signal
import sys
from collections.abc import Callable
from enum import StrEnum

# from pprint import pprint
from typing import Any, Awaitable, Optional, AsyncIterable

import aiohttp
import click
from aiofile import async_open
from loguru import logger
import uvloop
# wofür wird das BaseModel benutzt?
from pydantic import BaseModel, ConfigDict
from PIL import Image

import melvonaut.constants as con


##### LOGGING #####
logger.remove()
logger.add(sink=sys.stderr, level="DEBUG", backtrace=True, diagnose=True)
logger.add(
    sink=con.LOG_LOCATION,
    rotation="00:00",
    level="DEBUG",
    backtrace=True,
    diagnose=True,
)


##### ENUMS #####
# melvin satellite modes
class State(StrEnum):
    Deployment = "deployment"
    Acquisition = "acquisition"
    Charge = "charge"
    Safe = "safe"
    Communication = "communication"
    Transition = "transition"
    Unknown = "none"
# melvin lenses
class Angle(StrEnum):
    Wide = "wide"
    Narrow = "narrow"
    Normal = "normal"
    Unknown = "unknown"
# part of melvins state machine
class MELVINTasks(StrEnum):
    Mapping = "mapping"
    Emergencies = "emergencies"
    events = "events"
    idle = "idle"
# helper for images??
class MelvinImage(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    image: Image.Image
    angle: Angle
    cor_x: float
    cor_y: float
    time: datetime.datetime


##### Global Variables #####
loop = uvloop.new_event_loop()
current_telemetry = None
state_planner = None

##### TELEMETRY #####
class Telemetry(BaseModel):

    # helper enum for Telemetry
    class AreaCovered(BaseModel):
        narrow: float
        normal: float
        wide: float
    # helper enum for Telemetry
    class DataVolume(BaseModel):
        data_volume_received: int
        data_volume_sent: int

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


##### Timer #####
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


##### State machine #####
class StatePlanner(BaseModel):
    current_telemetry: Optional[Telemetry] = None
    previous_telemetry: Optional[Telemetry] = None

    previous_state: Optional[State] = None
    state_change_time: datetime.datetime = datetime.datetime.now()

    submitted_transition_request: bool = False

    target_state: Optional[State] = None

    melvin_task: MELVINTasks = MELVINTasks.Mapping

    def get_current_state(self) -> State:
        if self.current_telemetry is None:
            return State.Unknown
        return self.current_telemetry.state

    def get_previous_state(self) -> State:
        if self.previous_telemetry is None:
            return State.Unknown
        return self.previous_telemetry.state

    def get_simulation_speed(self) -> int:
        if self.current_telemetry is None:
            return 1
        return self.current_telemetry.simulation_speed

    def get_time_since_state_change(self) -> datetime.timedelta:
        return datetime.datetime.now() - self.state_change_time

    def calc_transition_remaining_time(self) -> datetime.timedelta:
        if self.get_current_state() is State.Transition:
            logger.debug("Not in transition state, returning 0")
            return datetime.timedelta(0)
        elif self.previous_state is State.Safe:
            total_time = datetime.timedelta(
                seconds=con.STATE_TRANSITION_FROM_SAFE_TIME
                / self.get_simulation_speed()
            )
            return total_time - self.get_time_since_state_change()
        else:
            total_time = datetime.timedelta(
                seconds=con.STATE_TRANSITION_TIME / self.get_simulation_speed()
            )
            return total_time - self.get_time_since_state_change()

    async def trigger_state_transition(self, new_state: State) -> None:
        if new_state in [State.Transition, State.Unknown, State.Deployment, State.Safe]:
            logger.warning(f"Cannot transition to {new_state}.")
        if self.current_telemetry is None:
            logger.warning("No telemetry data available. Cannot initiate transition.")
            return
        request_body = {
            "state": new_state,
            "vel_x": self.current_telemetry.vx,
            "vel_y": self.current_telemetry.vy,
            "camera_angle": self.current_telemetry.angle,
        }
        async with aiohttp.ClientSession() as session:
            async with session.put(con.CONTROL_ENDPOINT, json=request_body) as response:
                if response.status == 200:
                    logger.info(
                        f"Started transition to {new_state} at battery level {self.current_telemetry.battery}"
                    )
                    self.submitted_transition_request = True
                    self.target_state = new_state
                else:
                    logger.warning(
                        f"Failed to transition to {new_state}: {response.status}"
                    )
                    logger.debug(f"Response body: {await response.text()}")

    async def switch_if_battery_low(
        self, state_low_battery: State, state_high_battery: State
    ) -> None:
        if self.current_telemetry is None:
            logger.warning(
                "No telemetry data available. Cannot plan battery based switching."
            )
            return
        if self.current_telemetry.battery <= con.BATTERY_LOW_THRESHOLD:
            if self.get_current_state() is state_low_battery:
                return
            logger.debug(
                f"State is {self.get_current_state()}, Battery is low, triggering transition to {state_low_battery}"
            )
            await self.trigger_state_transition(state_low_battery)
        else:
            if self.get_current_state() is state_high_battery:
                return
            logger.debug(
                f"State is {self.get_current_state()}, Battery is high, triggering transition to {state_high_battery}"
            )
            await self.trigger_state_transition(state_high_battery)

    async def plan_state_switching(self) -> None:
        if self.current_telemetry is None:
            logger.warning("No telemetry data available. Cannot plan state switching.")
            return

        state = self.get_current_state()

        match self.melvin_task:
            case MELVINTasks.Mapping:
                match state:
                    case State.Transition:
                        logger.info(
                            f"State is Transition to {self.target_state}, waiting for transition to complete"
                        )
                        logger.debug(
                            f"Time since state change: {self.get_time_since_state_change()}"
                        )
                        expected_time_to_complete = (
                            self.calc_transition_remaining_time()
                        )
                        logger.info(
                            f"Expected time to complete state transition: {expected_time_to_complete}"
                        )
                        logger.debug(
                            f"Previous state: {self.get_previous_state()}, Current state: {self.get_current_state()}"
                        )
                    case State.Acquisition:
                        await self.switch_if_battery_low(
                            State.Charge, State.Acquisition
                        )
                        loop.create_task(self.run_get_image())
                    case State.Charge:
                        if (
                            self.current_telemetry.battery
                            >= self.current_telemetry.max_battery
                            - con.BATTERY_HIGH_THRESHOLD
                        ):
                            await self.trigger_state_transition(State.Acquisition)
                    case State.Safe:
                        # Transitioning directly to Acquisition is somehow bugged when safe was triggered due to empty battery
                        # await self.switch_if_battery_low(State.Charge, State.Acquisition)
                        logger.debug("State is Safe, triggering transition to Charge")
                        await self.trigger_state_transition(State.Communication)
                    case State.Communication:
                        await self.switch_if_battery_low(
                            State.Charge, State.Acquisition
                        )
                    case State.Deployment:
                        logger.debug(
                            "State is Deployment, triggering transition to Acquisition"
                        )
                        await self.trigger_state_transition(State.Acquisition)
                    case _:
                        logger.warning(f"Unknown state {state}")
            case MELVINTasks.Emergencies:
                pass
            case MELVINTasks.events:
                pass
            case MELVINTasks.idle:
                pass

    async def update_telemetry(self, new_telemetry: Telemetry) -> None:
        self.previous_telemetry = self.current_telemetry
        self.current_telemetry = new_telemetry

        logger.debug(
            f"State: {self.get_current_state()},"
            f" Battery level: {self.current_telemetry.battery}/{self.current_telemetry.max_battery}"
        )

        if self.previous_telemetry is not None:
            if self.previous_telemetry.state != self.current_telemetry.state:
                logger.info(
                    f"State changed from {self.previous_telemetry.state} to {self.current_telemetry.state}"
                )
                self.previous_state = self.previous_telemetry.state
                self.state_change_time = datetime.datetime.now()
                if self.current_telemetry.state is State.Transition:
                    if self.submitted_transition_request:
                        self.submitted_transition_request = False
                    else:
                        logger.warning("State transition was externally triggered!")
                elif (
                    self.get_previous_state() is State.Transition
                    and self.get_current_state() is not State.Transition
                ):
                    if self.get_current_state() is self.target_state:
                        logger.debug(
                            f"Planned state transition to {self.target_state} completed"
                        )
                    else:
                        logger.warning(
                            "Planned state transition to {self.target_state} failed, now in {self.current_telemetry.state}"
                        )
                    self.target_state = None

                logger.debug(
                    f"Previous state: {self.previous_telemetry.state}, Current state: {self.current_telemetry.state}"
                )
            await self.plan_state_switching()

    async def get_image(self) -> None:
        if self.current_telemetry is None:
            logger.warning("No telemetry data available. Cannot get image.")
            return

        async with aiohttp.ClientSession() as session:
            async with session.get(con.IMAGE_ENDPOINT) as response:
                if response.status == 200:
                    logger.debug("Received image")
                    image_path = con.IMAGE_LOCATION.format(
                        angle=self.current_telemetry.angle,
                        cor_x=self.current_telemetry.width_x,
                        cor_y=self.current_telemetry.height_y,
                        time=datetime.datetime.now(),
                    )
                    async with async_open(image_path, "wb") as afp:
                        await afp.write(await response.content.read())
                else:
                    logger.warning(f"Failed to get image: {response.status}")
                    logger.debug(f"Response body: {await response.text()}")

    async def run_get_image(self) -> None:
        await self.get_image()
        while self.get_current_state() is State.Acquisition:
            delay_in_s = round(
                5 / self.get_simulation_speed()
            )  # TODO Replace with calculation based on distance traveled
            image_task = Timer(timeout=delay_in_s, callback=self.get_image).get_task()
            await asyncio.gather(image_task)

# remove once we have classes
state_planner = StatePlanner()


async def get_observations() -> None:
    async with aiohttp.ClientSession() as session:
        async with session.get(con.OBSERVATION_ENDPOINT) as response:
            if response.status == 200:
                json_response = await response.json()
                logger.info("Received observations")
                # pprint(json_response, indent=4, sort_dicts=True)
                await state_planner.update_telemetry(Telemetry(**json_response))
            else:
                logger.warning(f"Failed to get observations: {response.status}")


async def run_get_observations() -> None:
    await get_observations()
    while True:
        logger.info("Submitted observations request")
        observe_task = Timer(
            timeout=con.OBSERVATION_REFRESH_RATE, callback=get_observations
        ).get_task()
        await asyncio.gather(observe_task)


async def get_announcements() -> None:
    try:
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
    except TimeoutError:
        logger.info("Announcements subscription timed out")


async def run_get_announcements() -> None:
    logger.info("Started announcements subscription")
    while True:
        await asyncio.gather(get_announcements())
        logger.info("Restarted announcements subscription")



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
                angle = Angle(match.group(1))
                cor_x = float(match.group(2))
                cor_y = float(match.group(3))
                time = datetime.datetime.strptime(match.group(4), "%Y-%m-%d_%H-%M-%S")
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

    loop.create_task(run_get_observations())
    loop.create_task(run_get_announcements())

    loop.create_task(run_read_images())

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
