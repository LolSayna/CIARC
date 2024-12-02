import asyncio
import datetime
import time
from enum import StrEnum
from typing import Callable, Awaitable, Any

from PIL import Image
from pydantic import BaseModel, ConfigDict
from typing import Optional

from loguru import logger

# habe luhki nach loguru log rate limiter gefragt, gibt anscheinend keine besser inbuild lösung 
# mypy: ignore-errors
def log_rate_limiter(interval_seconds: int) -> function:
    def decorator(func) -> function:
        last_log_time = [0]  # Use a list to allow modification of non-local state

        def wrapper(*args, **kwargs) -> function:
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


# From User Manual
class CameraAngle(StrEnum):
    Wide = "wide"
    Narrow = "narrow"
    Normal = "normal"
    Unknown = "unknown"


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
    old_pos: tuple[int, int]
    older_pos: tuple[int, int]
    oldest_pos: tuple[int, int]
    last_timestamp: datetime.datetime

    pre_transition_state: State
    planed_transition_state: State
