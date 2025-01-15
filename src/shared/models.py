import asyncio
import datetime
import time
import requests
from enum import StrEnum
from typing import Callable, Awaitable, Any

from PIL import Image
from pydantic import BaseModel, ConfigDict
from typing import Optional

import shared.constants as con
from loguru import logger

# Fix issue with Image size
Image.MAX_IMAGE_PIXELS = 500000000


# From User Manual
class CameraAngle(StrEnum):
    Wide = "wide"
    Narrow = "narrow"
    Normal = "normal"
    Unknown = "unknown"


# calculates the distance between two coordinates, respecting overflows
# TODO not sure about this, need to think when i am awake
def calc_distance(a: int, b: int) -> int:
    if a > con.WORLD_X:
        a = a % con.WORLD_X
    elif a < 0:
        a += con.WORLD_X

    if b > con.WORLD_X:
        b = b % con.WORLD_X
    elif b < 0:
        b += con.WORLD_X

    return abs(a, b)


class ZonedObjective(BaseModel):
    id: int  # could be null acording to Dto
    name: str
    start: datetime.datetime
    end: datetime.datetime
    decrease_rate: float
    zone: Optional[tuple[int, int, int, int]]  # could be a str acording to dto
    optic_required: CameraAngle  # cast from str
    coverage_required: int
    description: str  # cast from str
    secret: bool
    # sprite is ignored as said in email


# extracts and parses objective format from the format given from its matching api endpoint
def parse_objective_api(
    objective_list: requests.models.Response,
) -> list[ZonedObjective]:
    z_obj_list = []
    # parse objective list
    for obj in objective_list["zoned_objectives"]:
        if type(obj["zone"]) is str:
            zone = None
        else:
            zone = (
                int(obj["zone"][0]),
                int(obj["zone"][1]),
                int(obj["zone"][2]),
                int(obj["zone"][3]),
            )

        z_obj_list.append(
            ZonedObjective(
                id=obj["id"],
                name=obj["name"],
                start=datetime.datetime.fromisoformat(obj["start"]),
                end=datetime.datetime.fromisoformat(obj["end"]),
                decrease_rate=obj["decrease_rate"],
                zone=zone,
                optic_required=CameraAngle(obj["optic_required"]),
                coverage_required=obj["coverage_required"],
                description=obj["description"],
                secret=obj["secret"],
            )
        )

    return sorted(z_obj_list, key=lambda event: event.start)


# habe luhki nach loguru log rate limiter gefragt, gibt anscheinend keine besser inbuild lösung
# mypy: ignore-errors
def log_rate_limiter(interval_seconds: int):
    def decorator(func):
        last_log_time = [0]  # Use a list to allow modification of non-local state

        def wrapper(*args, **kwargs):
            nonlocal last_log_time
            current_time = time.time()
            if current_time - last_log_time[0] >= interval_seconds:
                func(*args, **kwargs)
                last_log_time[0] = current_time

        return wrapper

    return decorator


# mypy: ignore-errors


@log_rate_limiter(3)  # Apply a 10-second rate limiter
def limited_log(message: str) -> None:
    logger.info(message)


@log_rate_limiter(1)  # Apply a 10-second rate limiter
def limited_log_debug(message: str) -> None:
    logger.debug(message)


# was kann das?
class Timer(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    _timeout: float
    _callback: Callable[[], Awaitable[Any]]
    _task: asyncio.Task[None]

    def __init__(self, timeout: float, callback: Callable[[], Awaitable[Any]]):
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


# Our custom programs/missions/states in which we can place Melvin
class MELVINTasks(StrEnum):
    Mapping = "mapping"
    Objectives_only = "objectives"
    Emergencies = "emergencies"
    Events = "events"
    Idle = "idle"


# From User Manual
class State(StrEnum):
    Deployment = "deployment"
    Acquisition = "acquisition"
    Charge = "charge"
    Safe = "safe"
    Communication = "communication"
    Transition = "transition"
    Unknown = "none"


# ISO 8601 format
# Melin returns like this: 2024-12-24T13:10:13.660337Z
#   or                     2024-12-26T13:00:00Z

# convert with datetime.datetime.fromisoformat(X)
#   2024-12-24 13:09:12.786576+00:00
#   2024-12-30 13:00:00+00:00


# NOT USED only for referenze
class MelvinTime(datetime.datetime):
    time: datetime.datetime


class MelvinImage(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    image: Image.Image
    angle: CameraAngle
    cor_x: int
    cor_y: int
    time: datetime.datetime


# based on /observation API endpoint
class BaseTelemetry(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    class AreaCovered(BaseModel):
        narrow: float
        normal: float
        wide: float

    class DataVolume(BaseModel):
        data_volume_received: int
        data_volume_sent: int

    active_time: float
    angle: CameraAngle
    area_covered: Optional[AreaCovered] = None
    battery: float
    data_volume: Optional[DataVolume] = None
    distance_covered: Optional[float] = None
    fuel: float
    width_x: int
    height_y: int
    images_taken: Optional[int] = None
    max_battery: float
    objectives_done: Optional[int] = None
    objectives_points: Optional[int] = None
    simulation_speed: int
    state: State
    timestamp: Optional[datetime.datetime] = None
    vx: float
    vy: float


# more Telemetry, used in Riftconsole to display map
# TODO only temporary so far
class Telemetry(BaseTelemetry):
    last_timestamp: datetime.datetime

    pre_transition_state: State
    planed_transition_state: State
