
##### State machine #####
import asyncio
import subprocess
import datetime
import math
import threading
import tracemalloc
from typing import Optional
from aiofile import async_open
import aiohttp
from pydantic import BaseModel

import shared.constants as con
from melvonaut.mel_telemetry import MelTelemetry
from shared.models import CameraAngle, MELVINTasks, State, Timer, ZonedObjective, lens_size_by_angle, limited_log, parse_objective_api
from loguru import logger
from melvonaut.loop_config import loop
import random


class StatePlanner(BaseModel):
    melv_id: int = random.randint(0, 9999)
    current_telemetry: Optional[MelTelemetry] = None
    previous_telemetry: Optional[MelTelemetry] = None

    previous_state: Optional[State] = None
    state_change_time: datetime.datetime = datetime.datetime.now()

    submitted_transition_request: bool = False

    target_state: Optional[State] = None

    _accelerating: bool = False

    _run_get_image_task: Optional[asyncio.Task[None]] = None

    _aiohttp_session: Optional[aiohttp.ClientSession] = None

    _target_vel_x: Optional[float] = None
    _target_vel_y: Optional[float] = None

    _z_obj_list: list[ZonedObjective] = []

    _current_obj_name: str = ""

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
        """Sets new values for accelartion, also set _accelerating"""

        self._target_vel_x = new_vel_x
        self._target_vel_y = new_vel_y

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
        """Tries to change the camera angle to new_angle"""
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
        # set if angle got set
        # TODO fix later
        #await loop.run_get_observations()
        #await loop.create_task(get_observations())

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

        match state:
            case State.Transition:
                logger.debug(
                    f"Time since state change: {self.get_time_since_state_change()}"
                )
                expected_time_to_complete = self.calc_transition_remaining_time()
                limited_log(
                    f"State is Transition to {self.target_state}, waiting for transition to complete.\nExpected time to complete state transition: {expected_time_to_complete}"
                )
                logger.debug(
                    f"Previous state: {self.get_previous_state()}, Current state: {self.get_current_state()}"
                )
            case State.Acquisition:
                await self.switch_if_battery_low(State.Charge, State.Acquisition)
            case State.Charge:
                if (
                    self.current_telemetry.battery
                    >= self.current_telemetry.max_battery - con.BATTERY_HIGH_THRESHOLD
                ):
                    await self.trigger_state_transition(State.Acquisition)
            case State.Safe:
                if self.current_telemetry.battery >= (
                    self.current_telemetry.max_battery * 0.5
                ):
                    await self.trigger_state_transition(State.Acquisition)
                else:
                    await self.trigger_state_transition(State.Charge)
                await self.switch_if_battery_low(State.Charge, State.Acquisition)
            case State.Communication:
                await self.switch_if_battery_low(State.Charge, State.Acquisition)
            case State.Deployment:
                logger.debug(
                    "State is Deployment, triggering transition to Acquisition"
                )
                await self.trigger_state_transition(State.Acquisition)

    async def update_telemetry(self, new_telemetry: MelTelemetry) -> None:
        self.previous_telemetry = self.current_telemetry
        self.current_telemetry = new_telemetry

        logger.debug(
            f"State: {self.get_current_state()},"
            f" Battery level: {self.current_telemetry.battery}/{self.current_telemetry.max_battery},"
            f" Vel X,Y: {self.current_telemetry.vx}, {self.current_telemetry.vy},"
            f" Fuel: {self.current_telemetry.fuel}"
        )

        # if self.get_current_state() == State.Acquisition:
        #    await self.get_image()
        logger.debug(f"Threads: {threading.active_count()}")
        # for thread in threading.enumerate():
        #    frame = sys._current_frames()[thread.ident]
        #    logger.warning(f"{inspect.getframeinfo(frame).filename}.{inspect.getframeinfo(frame).function}:{inspect.getframeinfo(frame).lineno}")

        # check if still accelerating
        if (
            self._target_vel_x == self.current_telemetry.vx
            and self._target_vel_y == self.current_telemetry.vy
        ):
            self._accelerating = False

        if self.previous_telemetry is not None:
            if self.get_previous_state() != self.get_current_state():
                logger.info(
                    f"State changed from {self.get_previous_state()} to {self.get_current_state()}"
                )
                self.previous_state = self.get_previous_state()
                self.state_change_time = datetime.datetime.now()
                # Put in here events to do on state change
                if con.TRACING:
                    if self.previous_state == State.Transition:
                        snapshot1 = tracemalloc.take_snapshot()
                        stats = snapshot1.statistics("traceback")
                        for stat in stats:
                            logger.warning(
                                "%s memory blocks: %.1f KiB"
                                % (stat.count, stat.size / 1024)
                            )
                            for line in stat.traceback.format():
                                logger.warning(line)

                logger.debug(
                    f"Previous state: {self.previous_state}, Current state: {self.get_current_state()}"
                )
                match self.get_current_state():
                    case State.Transition:
                        # if self._run_get_image_task:
                        #    self._run_get_image_task.cancel()
                        if self.submitted_transition_request:
                            self.submitted_transition_request = False
                        else:
                            logger.warning("State transition was externally triggered!")
                    case State.Acquisition:
                        logger.info("Starting control in acquisition state.")

                        loop.create_task(self.run_get_image())

                        await self.control_acquisition()
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
        if not self._aiohttp_session:
            self._aiohttp_session = aiohttp.ClientSession()

        # Filter out cases where no image should be taken

        if (
            (con.CURRENT_MELVIN_TASK == MELVINTasks.Fixed_objective or con.CURRENT_MELVIN_TASK == MELVINTasks.Next_objective)
            and not self._z_obj_list
        ):
            logger.warning(
                "Skipped image: In Objectives_only mode, but z_obj_list emtpy!"
            )
            return

        if self.current_telemetry.angle != con.TARGET_CAMERA_ANGLE_ACQUISITION:
            logger.info(
                f"Skipped image: current_angle={self.current_telemetry.angle} vs target={con.TARGET_CAMERA_ANGLE_ACQUISITION}"
            )
            return
        if self._accelerating:
            logger.info(
                f"Skipped image: accelerating to: {self._target_vel_x} {self._target_vel_y}"
            )
            return

        if con.DO_TIMING_CHECK and con.START_TIME > datetime.datetime.now(
            datetime.timezone.utc
        ):
            logger.warning(
                f"Skipped image, to early: start={con.START_TIME} current_time={datetime.datetime.now(datetime.timezone.utc)}"
            )
            return
        if (
            con.DO_TIMING_CHECK
            and datetime.datetime.now(datetime.timezone.utc) > con.STOP_TIME
        ):
            logger.warning(
                f"Skipped image, to late: end={con.STOP_TIME} current_time={datetime.datetime.now(datetime.timezone.utc)}"
            )
            return

        # save the current telemetry values, so they dont get overwritten by a later update
        tele_timestamp = self.current_telemetry.timestamp
        tele_x = self.current_telemetry.width_x
        tele_y = self.current_telemetry.height_y
        tele_vx = self.current_telemetry.vx
        tele_vy = self.current_telemetry.vy
        tele_simSpeed = self.get_simulation_speed()
        tele_angle = self.current_telemetry.angle

        lens_size = lens_size_by_angle(self.current_telemetry.angle)
        """
        # TODO add box check if melvin and objective overlap
        # check if we are in range of an objective
        # TODO also check MELVINTasks
        # TODO check if within box, unless hidden
        melvin_box = (
            tele_x - lens_size / 2,
            tele_y - lens_size / 2,
            tele_x + lens_size / 2,
            tele_y + lens_size / 2,
        )
        if self._z_obj_list[0].zone is None:
            logger.warning("Hidden objective, taking photo")
            return
            TODO
        else:
            logger.warning("Checking if in range of objective:")
            objective_box = self._z_obj_list[0].zone

        if not boxes_overlap_in_grid(melvin_box, objective_box):
            logger.error(
                f"Image skipped, not Overlapping! {melvin_box} {objective_box}"
            )
            return
        """
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(con.IMAGE_ENDPOINT) as response:
                    if response.status == 200:
                        # Extract exact image timestamp
                        img_timestamp = response.headers.get("image-timestamp")
                        if img_timestamp is None:
                            logger.error(
                                "Image timestamp not found in headers, substituting with current time"
                            )
                            parsed_img_timestamp = datetime.datetime.now()
                        else:
                            parsed_img_timestamp = datetime.datetime.fromisoformat(
                                img_timestamp
                            )

                        # Calculate the difference between the img and the last telemetry
                        difference_in_seconds = (
                            parsed_img_timestamp - tele_timestamp
                        ).total_seconds()

                        adj_x = round(
                            tele_x + (difference_in_seconds * tele_vx * tele_simSpeed)
                        ) - (lens_size / 2)
                        adj_y = round(
                            tele_y + (difference_in_seconds * tele_vy * tele_simSpeed)
                        ) - (lens_size / 2)

                        # TODO check if images are correct!
                        # TODO might also need modulo for side cases
                        logger.debug(f"T {parsed_img_timestamp} | C {tele_timestamp}")
                        logger.debug(
                            f"D {difference_in_seconds} | R {tele_x} ADJ {adj_x}"
                        )

                        image_path = con.IMAGE_LOCATION.format(
                            melv_id=self._current_obj_name,
                            angle=tele_angle,
                            time=parsed_img_timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f"),
                            cor_x=int(adj_x),
                            cor_y=int(adj_y),
                        )

                        logger.info(
                            f"Received image at {adj_x}x {adj_y}y with {self.current_telemetry.angle} angle"
                        )

                        async with async_open(image_path, "wb") as afp:
                            while True:
                                cnt = await response.content.readany()
                                if not cnt:
                                    break
                                await afp.write(cnt)
                    else:
                        logger.warning(f"Failed to get image: {response.status}")
                        logger.info(f"Response body: {await response.text()}")
                        logger.info(
                            "This is normal at the end of acquisition mode once."
                        )
            except aiohttp.client_exceptions.ConnectionTimeoutError:
                logger.warning("Observations endpoint timeouted.")
            except asyncio.exceptions.CancelledError:
                logger.warning("Get image task was cancelled.")

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

    # run once after changing into acquisition mode -> setup
    async def control_acquisition(self) -> None:
        async with aiohttp.ClientSession() as session:
            # update Objectives
            async with session.get(con.OBJECTIVE_ENDPOINT) as response:
                if response.status == 200:
                    json_response = await response.json()
                    self._z_obj_list: list[ZonedObjective] = parse_objective_api(
                        json_response
                    )
                    logger.warning(
                        f"Updated objectives, there are {len(self._z_obj_list)} objectives."
                    )
                else:
                    logger.error("Could not get OBJECTIVE_ENDPOINT")

        current_obj = None
        # Always check for new objective in this task
        if con.CURRENT_MELVIN_TASK == MELVINTasks.Next_objective:
            current_obj = self._z_obj_list[0]

            logger.error(f"Using next_objective, current task: {current_obj.name}")

        # In this task look for the given string
        elif con.CURRENT_MELVIN_TASK == MELVINTasks.Fixed_objective:

            for obj in self._z_obj_list:
                if obj.name == con.FIXED_OBJECTIVE:
                    logger.error(f"Using fixed_objective, current task: {obj}")
                    current_obj = obj
                    break

        if current_obj:

            con.START_TIME = current_obj.start
            con.STOP_TIME = current_obj.end
            con.TARGET_CAMERA_ANGLE_ACQUISITION = current_obj.optic_required

            self._current_obj_name = str(current_obj.id) + (current_obj.name).replace(
                " ", ""
            )

            con.IMAGE_PATH = con.IMAGE_PATH_BASE + self._current_obj_name + "/"

            con.IMAGE_LOCATION = (
                con.IMAGE_PATH + "image_{melv_id}_{angle}_{time}_x_{cor_x}_y_{cor_y}.png"
            )
            try:
                subprocess.run(["mkdir", con.IMAGE_PATH], check=True)
                logger.info(f"Created folder: {con.IMAGE_PATH}")

            except subprocess.CalledProcessError as e:
                logger.info(f"z_obj could not mkdir: {e}")


        # check if change occured and cut the last image

        await self.trigger_camera_angle_change(con.TARGET_CAMERA_ANGLE_ACQUISITION)

        # TODO stop velocity change if battery is low
        if self.current_telemetry.battery < 25:
            logger.error("Battery low, TODO")

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
