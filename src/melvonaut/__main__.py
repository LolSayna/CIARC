"""
Melvonaut



:author: Jonathan Decker
"""

import asyncio
import datetime
import io
import json
import math
import os
import re
import signal
import sys

from typing import Any, Optional, AsyncIterable

import aiohttp
import click
from aiofile import async_open
from loguru import logger
import uvloop
from pydantic import BaseModel
from PIL import Image
import aiodebug.log_slow_callbacks  # type: ignore


import shared.constants as con
from shared.models import (
    State,
    MELVINTasks,
    MelvinImage,
    Timer,
    CameraAngle,
    BaseTelemetry,
)

##### LOGGING #####
logger.remove()
logger.add(sink=sys.stderr, level="DEBUG", backtrace=True, diagnose=True)
logger.add(
    sink=con.MEL_LOG_LOCATION,
    rotation="00:00",
    level="DEBUG",
    backtrace=True,
    diagnose=True,
)

##### Global Variables #####
loop = uvloop.new_event_loop()
current_telemetry = None
aiodebug.log_slow_callbacks.enable(0.05)


##### TELEMETRY #####
class MelTelemetry(BaseTelemetry):
    timestamp: datetime.datetime

    async def store_observation(self) -> None:
        logger.debug("Storing observation")
        try:
            async with async_open(con.TELEMETRY_LOCATION, "r") as afp:
                raw_telemetry = await afp.read()
                dict_telemetry = json.loads(raw_telemetry)
        except FileNotFoundError:
            logger.debug(f"{con.TELEMETRY_LOCATION} does not exist.")
            dict_telemetry = {}

        if self.timestamp:
            timestamp = self.timestamp.isoformat()
        else:
            timestamp = datetime.datetime.now().isoformat()
        new_telemetry_entry = self.model_dump(exclude={"timestamp"})
        dict_telemetry[timestamp] = new_telemetry_entry
        json_telemetry = json.dumps(dict_telemetry, indent=4, sort_keys=True)

        async with async_open(con.TELEMETRY_LOCATION, "w") as afp:
            logger.debug(f"Writing to {con.TELEMETRY_LOCATION}")
            await afp.write(str(json_telemetry))
        logger.debug("Observation stored")

    def model_post_init(self, __context__: Any) -> None:
        loop.create_task(self.store_observation())


##### State machine #####
class StatePlanner(BaseModel):
    current_telemetry: Optional[MelTelemetry] = None
    previous_telemetry: Optional[MelTelemetry] = None

    previous_state: Optional[State] = None
    state_change_time: datetime.datetime = datetime.datetime.now()

    submitted_transition_request: bool = False

    target_state: Optional[State] = None

    melvin_task: MELVINTasks = MELVINTasks.Mapping

    _accelerating: bool = False

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
        elif self.previous_state == State.Safe:
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

    def calc_current_location(self) -> tuple[float, float]:
        if self.current_telemetry is None:
            return 0.0, 0.0
        time_since_observation = (
            datetime.datetime.now() - self.current_telemetry.timestamp
        ).total_seconds()
        current_x = (
            self.current_telemetry.width_x
            + self.current_telemetry.vx * time_since_observation
        )
        current_y = (
            self.current_telemetry.height_y
            + self.current_telemetry.vy * time_since_observation
        )
        return current_x, current_y

    async def trigger_velocity_change(self, new_vel_x: float, new_vel_y: float) -> None:
        if self.current_telemetry is None:
            logger.warning("No telemetry data available. Cannot set velocity.")
            return
        if (
            new_vel_x == self.current_telemetry.vx
            and new_vel_y == self.current_telemetry.vy
        ):
            self._accelerating = False
            logger.info("Target velocity already set. Not changing velocity.")
            return
        request_body = {
            "vel_x": new_vel_x,
            "vel_y": new_vel_y,
            "camera_angle": self.current_telemetry.angle,
            "state": self.get_current_state(),
        }
        async with aiohttp.ClientSession() as session:
            async with session.put(con.CONTROL_ENDPOINT, json=request_body) as response:
                if response.status == 200:
                    self._accelerating = True
                    logger.info(f"Velocity set to {new_vel_x}, {new_vel_y}")
                else:
                    logger.error(f"Failed to set velocity to {new_vel_x}, {new_vel_y}")

    async def trigger_camera_angle_change(self, new_angle: CameraAngle) -> None:
        if self.current_telemetry is None:
            logger.warning("No telemetry data available. Cannot set camera angle.")
            return
        if new_angle == self.current_telemetry.angle:
            logger.info("Target camera angle already set. Not changing angle.")
            return
        request_body = {
            "vel_x": self.current_telemetry.vx,
            "vel_y": self.current_telemetry.vy,
            "camera_angle": new_angle,
            "state": self.get_current_state(),
        }
        async with aiohttp.ClientSession() as session:
            async with session.put(con.CONTROL_ENDPOINT, json=request_body) as response:
                if response.status == 200:
                    logger.info(f"Camera angle set to {new_angle}")
                else:
                    logger.error(f"Failed to set camera angle to {new_angle}")

    async def trigger_state_transition(self, new_state: State) -> None:
        if new_state in [State.Transition, State.Unknown, State.Deployment, State.Safe]:
            logger.warning(f"Cannot transition to {new_state}.")
            return
        if self.current_telemetry is None:
            logger.warning("No telemetry data available. Cannot initiate transition.")
            return
        if self.current_telemetry.state == State.Transition:
            logger.debug("Already in transition state, not starting transition.")
            return
        if new_state == self.get_current_state():
            logger.debug(f"State is already {new_state}, not starting transition.")
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
            if self.get_current_state() == state_low_battery:
                return
            logger.debug(
                f"State is {self.get_current_state()}, Battery is low, triggering transition to {state_low_battery}"
            )
            await self.trigger_state_transition(state_low_battery)
        else:
            if self.get_current_state() == state_high_battery:
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
                    case State.Charge:
                        if (
                            self.current_telemetry.battery
                            >= self.current_telemetry.max_battery
                            - con.BATTERY_HIGH_THRESHOLD
                        ):
                            await self.trigger_state_transition(State.Acquisition)
                    case State.Safe:
                        if self.current_telemetry.battery >= (
                            self.current_telemetry.max_battery * 0.5
                        ):
                            await self.trigger_state_transition(State.Acquisition)
                        else:
                            await self.trigger_state_transition(State.Charge)
                        await self.switch_if_battery_low(
                            State.Charge, State.Acquisition
                        )
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
            case MELVINTasks.Events:
                pass
            case MELVINTasks.Idle:
                pass

    async def update_telemetry(self, new_telemetry: MelTelemetry) -> None:
        self.previous_telemetry = self.current_telemetry
        self.current_telemetry = new_telemetry

        logger.debug(
            f"State: {self.get_current_state()},"
            f" Battery level: {self.current_telemetry.battery}/{self.current_telemetry.max_battery},"
            f" Vel X,Y: {self.current_telemetry.vx}, {self.current_telemetry.vy},"
            f" Fuel: {self.current_telemetry.fuel}"
        )

        if self.previous_telemetry is not None:
            if self.get_previous_state() != self.get_current_state():
                logger.info(
                    f"State changed from {self.get_previous_state()} to {self.get_current_state()}"
                )
                self.previous_state = self.get_previous_state()
                self.state_change_time = datetime.datetime.now()
                # Put in here events to do on state change
                logger.debug(
                    f"Previous state: {self.previous_state}, Current state: {self.get_current_state()}"
                )
                match self.get_current_state():
                    case State.Transition:
                        if self.submitted_transition_request:
                            self.submitted_transition_request = False
                        else:
                            logger.warning("State transition was externally triggered!")
                    case State.Acquisition:
                        logger.info("Starting control in acquisition state.")
                        loop.create_task(self.run_get_image())
                        await self.control_acquisition()
                        pass
                    case State.Charge:
                        pass
                    case State.Safe:
                        logger.warning("State transitioned to SAFE!")
                    case State.Communication:
                        pass
                    case State.Deployment:
                        logger.warning("State transitioned to DEPLOYMENT!")
                    case _:
                        logger.warning(f"Unknown state {self.get_current_state()}")
                if self.get_current_state() != State.Acquisition:
                    self._accelerating = False
                if self.get_current_state() != State.Transition:
                    if self.target_state != self.get_current_state():
                        logger.warning(
                            f"Planned state transition to {self.target_state} failed, now in {self.get_current_state()}"
                        )
                    else:
                        logger.debug(
                            f"Planned state transition to {self.target_state} succeeded."
                        )
                    self.target_state = None

            await self.plan_state_switching()

    async def get_image(self) -> None:
        if self.current_telemetry is None:
            logger.warning("No telemetry data available. Cannot get image.")
            return

        async with aiohttp.ClientSession() as session:
            async with session.get(con.IMAGE_ENDPOINT) as response:
                if response.status == 200:
                    # Extract exact image timestamp
                    img_timestamp = response.headers.get("image-timestamp")
                    if img_timestamp is None:
                        logger.warning(
                            "Image timestamp not found in headers, substituting with current time"
                        )
                        parsed_img_timestamp = datetime.datetime.now()
                    else:
                        parsed_img_timestamp = datetime.datetime.fromisoformat(
                            img_timestamp
                        )

                    # Calculate the difference between the img and the last telemetry
                    if self.current_telemetry.timestamp:
                        difference_in_seconds = (
                            parsed_img_timestamp - self.current_telemetry.timestamp
                        ).total_seconds()
                    else:
                        difference_in_seconds = (
                            parsed_img_timestamp - datetime.datetime.now()
                        ).total_seconds()

                    cor_x = round(
                        self.current_telemetry.width_x
                        + (
                            difference_in_seconds
                            * self.current_telemetry.vx
                            * self.get_simulation_speed()
                        )
                    )
                    cor_y = round(
                        self.current_telemetry.height_y
                        + (
                            difference_in_seconds
                            * self.current_telemetry.vy
                            * self.get_simulation_speed()
                        )
                    )
                    image_path = con.IMAGE_LOCATION.format(
                        angle=self.current_telemetry.angle,
                        cor_x=cor_x,
                        cor_y=cor_y,
                        time=img_timestamp,  # or should it be parsed_img_timestamp?
                    )
                    logger.debug(f"Received image at {cor_x}x{cor_y}y")
                    async with async_open(image_path, "wb") as afp:
                        await afp.write(await response.content.read())
                else:
                    logger.debug(f"Failed to get image: {response.status}")
                    logger.debug(f"Response body: {await response.text()}")

    async def run_get_image(self) -> None:
        await self.get_image()
        while self.get_current_state() == State.Acquisition:
            if self.current_telemetry is None:
                logger.warning(
                    f"No telemetry data available. Waiting {con.OBSERVATION_REFRESH_RATE}s for next image."
                )
                image_task = Timer(
                    timeout=con.OBSERVATION_REFRESH_RATE, callback=self.get_image
                ).get_task()
                await asyncio.gather(image_task)
                continue
            current_total_vel = self.current_telemetry.vx + self.current_telemetry.vy
            if self._accelerating:
                # If accelerating calculate distance based on current speed and acceleration
                delay_in_s = (
                    math.sqrt(
                        current_total_vel**2
                        + 2 * con.ACCELERATION * con.DISTANCE_BETWEEN_IMAGES
                    )
                    - current_total_vel
                ) / con.ACCELERATION
            else:
                # When not accelerating calculate distance based on current speed
                delay_in_s = float(con.DISTANCE_BETWEEN_IMAGES) / current_total_vel
            delay_in_s = delay_in_s / self.get_simulation_speed()
            logger.debug(f"Next image in {delay_in_s}s.")
            image_task = Timer(timeout=delay_in_s, callback=self.get_image).get_task()
            await asyncio.gather(image_task)

    async def control_acquisition(self) -> None:
        match self.melvin_task:
            case MELVINTasks.Mapping:
                await self.trigger_camera_angle_change(
                    con.TARGET_CAMERA_ANGLE_ACQUISITION
                )
                match con.TARGET_CAMERA_ANGLE_ACQUISITION:
                    case CameraAngle.Wide:
                        await self.trigger_velocity_change(
                            con.TARGET_SPEED_WIDE_X, con.TARGET_SPEED_WIDE_Y
                        )
                    case CameraAngle.Narrow:
                        await self.trigger_velocity_change(
                            con.TARGET_SPEED_NARROW_X, con.TARGET_SPEED_NARROW_Y
                        )
                    case CameraAngle.Normal:
                        await self.trigger_velocity_change(
                            con.TARGET_SPEED_NORMAL_X, con.TARGET_SPEED_NORMAL_Y
                        )
                    case _:
                        pass
            case MELVINTasks.Emergencies:
                pass
            case MELVINTasks.Events:
                pass
            case MELVINTasks.Idle:
                pass


state_planner = StatePlanner()


async def get_observations() -> None:
    async with aiohttp.ClientSession() as session:
        async with session.get(con.OBSERVATION_ENDPOINT) as response:
            if response.status == 200:
                json_response = await response.json()
                logger.debug("Received observations")
                # pprint(json_response, indent=4, sort_dicts=True)
                await state_planner.update_telemetry(MelTelemetry(**json_response))
            else:
                logger.warning(f"Failed to get observations: {response.status}")


async def run_get_observations() -> None:
    await get_observations()
    while True:
        logger.debug("Submitted observations request")
        observe_task = Timer(
            timeout=con.OBSERVATION_REFRESH_RATE / state_planner.get_simulation_speed(),
            callback=get_observations,
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
                        clean_line = line.decode("utf-8").strip().replace("data:", "")
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
                angle = CameraAngle(match.group(1))
                cor_x = int(match.group(2))
                cor_y = int(match.group(3))
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
