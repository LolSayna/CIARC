import asyncio
import csv
import datetime
import re
import time
from loguru import logger
from pathlib import Path
from enum import Enum, StrEnum
from typing import Callable, Awaitable, Any

from PIL import Image
from aiofile import async_open
from pydantic import BaseModel, ConfigDict
from typing import Optional, Union

import shared.constants as con

# Pillow  has a low default maximum image size, overwriten here
Image.MAX_IMAGE_PIXELS = 500000000


# [From CIARC API User Manual]
class CameraAngle(StrEnum):
    """
    Different camera angles possible on MELVIN.
    """

    Wide = "wide"
    Narrow = "narrow"
    Normal = "normal"
    Unknown = "unknown"


class State(StrEnum):
    """From CIARC user manual"""

    Deployment = "deployment"
    Acquisition = "acquisition"
    Charge = "charge"
    Safe = "safe"
    Communication = "communication"
    Transition = "transition"
    Unknown = "none"


class Slot(BaseModel):
    """
    One communication slot in which MELVIN can be contacted.

    Methods:
        parse_api(data: dict) -> tuple[int, list["Slot"]]:
            Parses the given API data to extract slots and the number of slots used.
    """

    id: int
    start: datetime.datetime
    end: datetime.datetime
    enabled: bool

    @staticmethod
    def parse_api(data: dict) -> tuple[int, list["Slot"]]:  # type: ignore
        """
        Parses CIARC API response into the list of available slots.

        Args:
            data (dict): The API response from /slots.

        Returns:
            tuple[int, list["Slot"]]: Number of communication slots used and
                list of slots sorted by the earliest start time.

        """
        slots_used = data["communication_slots_used"]
        slots = []
        for s in data["slots"]:
            slots.append(Slot(**s))

        slots.sort(key=lambda slot: slot.start)
        # logger.debug(f"Deparsed Slot API used: {slots_used} - {slots}")
        return (slots_used, slots)


class ZonedObjective(BaseModel):
    """
    One hidden or visible objective, completed by taking pictures of its position.
    """

    id: int  # could be null acording to Dto
    name: str
    start: datetime.datetime
    end: datetime.datetime
    decrease_rate: float
    zone: Optional[tuple[int, int, int, int]]  # could be a str acording to dto
    optic_required: CameraAngle  # cast from str
    coverage_required: float
    description: str  # cast from str
    secret: bool
    # sprite is ignored as said in email

    @staticmethod
    def parse_api(data: dict) -> list["ZonedObjective"]:  # type: ignore
        """
        Extracts and parses objectives from its matching api endpoint
        """
        z_obj_list = []
        # parse objective list
        for obj in data["zoned_objectives"]:
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


class BeaconObjective(BaseModel):
    """
    Emergency beacon objective from CIARC API.
    """

    id: int
    name: str
    start: datetime.datetime
    end: datetime.datetime
    decrease_rate: float
    attempts_made: int
    description: str

    @staticmethod
    def parse_api(data: dict) -> list["BeaconObjective"]:  # type: ignore
        """
        Parse CIARC API to list of this class
        """
        beacon_obj = []
        for b in data["beacon_objectives"]:
            beacon_obj.append(BeaconObjective(**b))

        return sorted(beacon_obj, key=lambda event: event.start)


class Achievement(BaseModel):
    """
    From CIARC API.
    """

    name: str
    done: bool
    points: int
    description: str
    goal_parameter_threshold: Union[bool, int, float, str]
    goal_parameter: Union[bool, int, float, str]

    @staticmethod
    def parse_api(data: dict) -> list["Achievement"]:  # type: ignore
        """
        Parse CIARC API into list of Achievment.
        """
        achv = []
        for a in data["achievements"]:
            achv.append(Achievement(**a))

        return achv


class HttpCode(Enum):
    """Used HTTP codes for API."""

    GET = "get"
    PUT = "put"
    DELETE = "delete"
    POST = "post"


# based on /observation API endpoint
class BaseTelemetry(BaseModel):
    """Based on /observation endpoint."""

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
    width_x: int
    height_y: int
    images_taken: int
    max_battery: float
    objectives_done: int
    objectives_points: int
    simulation_speed: int
    state: State
    timestamp: datetime.datetime
    vx: float
    vy: float

    def __str__(self) -> str:
        return (
            f"Telemetry@{self.timestamp.isoformat()} state={self.state} angle={self.angle} "
            f"(x,y)=({self.width_x},{self.height_y}) (vx,vy)=({self.vx},{self.vy}) "
            f"battery={self.battery}/{self.max_battery} fuel={self.fuel} sim_speed={self.simulation_speed} "
            f"dist_cov={self.distance_covered} area_cov={self.area_covered.narrow}/{self.area_covered.normal}/{self.area_covered.wide} "
            f"active_t={self.active_time} #images={self.images_taken} obj-done/points={self.objectives_done}/{self.objectives_points} "
            f"data-s/r={self.data_volume.data_volume_sent}/{self.data_volume.data_volume_received}"
        )


# [MELVONAUT]
class MELVINTask(StrEnum):
    """
    Our custom programs/missions/states in which we can place Melvin.
    In evaluation phase only mapping and ebt was used.
    The other two were used in Phase 2, or could be used in a future update.
    """

    Mapping = "mapping"
    Next_objective = "next_objective"
    Fixed_objective = "fixed_objective"
    EBT = "ebt"
    # Emergencies = "emergencies"
    # Events = "events"
    # Idle = "idle"


"""
def boxes_overlap_in_grid(box1, box2):
    
    # Not completed helper function.
    # Idea was to check if melvins camera range overlaps with an objective.
    
    grid_width = con.WORLD_X
    grid_height = con.WORLD_Y
    # Extract the position and dimensions of box1
    x1, y1, width1, height1 = box1
    # Extract the position and dimensions of box2
    x2, y2, width2, height2 = box2

    # Define a helper function to check overlap in one dimension with overflow
    def overlap_1d(start1, length1, start2, length2, max_length):
        # Compute the end positions with wrapping
        end1 = (start1 + length1 - 1) % max_length
        end2 = (start2 + length2 - 1) % max_length

        # Check overlap considering wrapping
        return (
            (start1 <= end2 and end1 >= start2)  # direct overlap
            or (
                end1 < start1 and (start1 <= end2 or end1 >= start2)
            )  # wrapped around for first box
            or (
                end2 < start2 and (start2 <= end1 or end2 >= start1)
            )  # wrapped around for second box
        )

    # Check overlap in both dimensions
    overlap_x = overlap_1d(x1, width1, x2, width2, grid_width)
    overlap_y = overlap_1d(y1, height1, y2, height2, grid_height)

    # The boxes overlap if they overlap in both dimensions
    return overlap_x and overlap_y
"""


def lens_size_by_angle(angle: CameraAngle) -> int:
    """
    Returns covered area by a single picture.
    """
    match angle:
        case CameraAngle.Narrow:
            lens_size = 600
        case CameraAngle.Normal:
            lens_size = 800
        case CameraAngle.Wide:
            lens_size = 1000
    return lens_size


def log_rate_limiter(interval_seconds: int):  # type: ignore
    """
    Limits how often a single event can trigger a lot entry. Prevents cluttering of the same message.
    Probaly not a "good" final solution.
    """

    # habe luhki nach loguru log rate limiter gefragt, gibt anscheinend keine besser inbuild lösung
    def decorator(func):  # type: ignore
        last_log_time = [0]  # Use a list to allow modification of non-local state

        def wrapper(*args, **kwargs):  # type: ignore
            nonlocal last_log_time
            current_time = time.time()
            if current_time - last_log_time[0] >= interval_seconds:
                func(*args, **kwargs)
                last_log_time[0] = current_time  # type: ignore

        return wrapper

    return decorator


# Apply a 3-second rate limiter
@log_rate_limiter(3)  # type: ignore
def limited_log(message: str) -> None:
    """Log limit for info"""
    logger.info(message)


# Apply a 1-second rate limiter
@log_rate_limiter(1)  # type: ignore
def limited_log_debug(message: str) -> None:
    """Log limit for debug"""
    logger.debug(message)


class Timer(BaseModel):
    """Starts tasks after a given intervall. E.g. take the next picture X-seconds after the current one."""

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


class MelvinImage(BaseModel):
    """Our format for a single image taken by MELVIN."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    image: Image.Image
    angle: CameraAngle
    cor_x: int
    cor_y: int
    time: datetime.datetime


class Ping:
    """Part of EBT objective, one single distance/ping."""

    def __init__(self, x: int, y: int, d: float, mind: int, maxd: int):
        self.x = x
        self.y = y
        self.d = d
        self.mind = mind
        self.maxd = maxd

    def __str__(self) -> str:
        return f"Ping: x={self.x}, y={self.y}, d={self.d}, mind={self.mind}, maxd={self.maxd}"


class Event(BaseModel):
    """Message by /announcements, includes time and position for ebt processing."""

    event: str
    id: int
    timestamp: Optional[datetime.datetime] = None
    current_x: Optional[float] = None
    current_y: Optional[float] = None

    def __str__(self) -> str:
        return f"Event: {self.event} (x,y)=({self.current_x},{self.current_y}) t={time_seconds(self.timestamp or live_utc())}"

    def easy_parse(self) -> tuple[float, float, float]:
        """Custom parsing wrapper for ebt calculation."""
        pattern = r"DISTANCE_(\d+\.\d+)"
        dist = re.findall(pattern, self.event)[0]
        if dist and self.current_x and self.current_y:
            return (float(dist), self.current_x, self.current_y)
        else:
            logger.warning(f"Tried to parse incomplete event: {self}")
            return (0.0, 0.0, 0.0)

    async def to_csv(self) -> None:
        """Melvonaut saves events."""
        event_dict = self.model_dump()
        if self.timestamp:
            event_dict["timestamp"] = self.timestamp.isoformat()
        if not Path(con.EVENT_LOCATION_CSV).is_file():
            async with async_open(con.EVENT_LOCATION_CSV, "w") as afp:
                writer = csv.DictWriter(afp, fieldnames=event_dict.keys())
                await writer.writeheader()
                await writer.writerow(event_dict)
            # logger.debug(f"Writing event to {con.EVENT_LOCATION_CSV}")
        else:
            async with async_open(con.EVENT_LOCATION_CSV, "a") as afp:
                writer = csv.DictWriter(afp, fieldnames=event_dict.keys())
                await writer.writerow(event_dict)
            # logger.debug(f"Writing event to {con.EVENT_LOCATION_CSV}")

    @staticmethod
    def load_events_from_csv(path: str) -> list["Event"]:
        """Melvonaut saves events as csv, Rift-console loads them."""
        events = []
        if not Path(path).is_file():
            logger.warning(f"No event file found under {path}")
        else:
            with open(path, "r") as f:
                for row in csv.DictReader(f):
                    read_event = Event(
                        event=row["event"],
                        id=int(row["id"]),
                        timestamp=datetime.datetime.fromisoformat(row["timestamp"]),
                        current_x=float(row["current_x"]),
                        current_y=float(row["current_y"]),
                    )
                    events.append(read_event)
            logger.info(f"Loaded {len(events)} events from {path}")
        return events


# [TIMEFORMATS]
# ISO 8601 format
# Melin returns like this: 2024-12-24T13:10:13.660337Z
#   or                     2024-12-26T13:00:00Z
# Z equivalent to +00:00 to indicate UTC timezone

# To get current time in UTC use datetime.datetime.now(datetime.timezone.utc)
# or get from string with datetime.datetime.fromisoformat(X)
# to also change into isoformat use X.isoformat()


# TARGET: 2025-03-01T00:54:02.809428+00:00
def live_utc() -> datetime.datetime:
    """Returns live datetime object, including timezone utc"""
    return datetime.datetime.now(datetime.timezone.utc)


def time_seconds(date: datetime.datetime) -> str:
    return date.strftime("%Y-%m-%dT%H:%M:%S")
