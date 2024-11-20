import asyncio
import datetime
from enum import StrEnum
from typing import Callable, Awaitable, Any

from PIL import Image
from pydantic import BaseModel, ConfigDict


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


class MELVINTasks(StrEnum):
    Mapping = "mapping"
    Emergencies = "emergencies"
    events = "events"
    idle = "idle"


class State(StrEnum):
    Deployment = "deployment"
    Acquisition = "acquisition"
    Charge = "charge"
    Safe = "safe"
    Communication = "communication"
    Transition = "transition"
    Unknown = "none"


class CameraAngle(StrEnum):
    Wide = "wide"
    Narrow = "narrow"
    Normal = "normal"
    Unknown = "unknown"


class MelvinImage(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    image: Image.Image
    angle: CameraAngle
    cor_x: float
    cor_y: float
    time: datetime.datetime


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
    area_covered: AreaCovered
    battery: float
    data_volume: DataVolume
    distance_covered: float
    fuel: float
    width_x: float
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


class Telemetry(BaseTelemetry):
    old_pos: tuple[float, float]
    older_pos: tuple[float, float]
    oldest_pos: tuple[float, float]
    last_timestamp: datetime.datetime

    pre_transition_state: State
    planed_transition_state: State
