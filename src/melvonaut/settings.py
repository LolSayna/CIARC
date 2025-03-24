# Our settings, could be changed later
import datetime
import json
import pathlib
from json import JSONDecodeError
from typing import Optional, Any

from dotenv import load_dotenv
import os

from pydantic import BaseModel

from shared.models import CameraAngle, MELVINTask
from shared import constants as con
from loguru import logger

load_dotenv()

file_log_handler_id = None


class Settings(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    ## [General Settings]

    OBSERVATION_REFRESH_RATE: int = 5  # Seconds between observation requests
    BATTERY_LOW_THRESHOLD: int = 20
    BATTERY_HIGH_THRESHOLD: int = 0  # Difference to Max Battery before switching

    TRACING: bool = False

    TERMINAL_LOGGING_LEVEL: str = "INFO"
    FILE_LOGGING_LEVEL: str = "DEBUG"

    API_PORT: int = 8080

    DISCORD_WEBHOOK_TOKEN: Optional[str] = os.getenv("DISCORD_WEBHOOK_TOKEN", None)
    DISCORD_ALERTS_ENABLED: bool = True

    NETWORK_SIM_ENABLED: bool = False

    ## [Camera Settings]
    TARGET_ANGLE_DEG: float = 23.0
    # With total speed over 50, cannot use wide angle camera
    # 49.9 = y + x
    # x = 2.35585 * y
    # 49.9 = 2.35585 * y + y
    # 49.9 = 3.35585 * y
    # y = 49.9 / 3.35585
    # y = 14.87
    # 49.9 - 14.87 = 35.03 = x
    TARGET_SPEED_NORMAL_X: float = 35.03  # 2.35585 times as much as Y
    TARGET_SPEED_NORMAL_Y: float = 14.87

    # With total speed over 10, cannot use narrow angle camera
    # 9.9 = y + x
    # y = 9.9 / 3.35585
    # y = 2.95
    # 9.9 - 2.95 = 6.95 = x
    TARGET_SPEED_NARROW_X: float = 6.95
    TARGET_SPEED_NARROW_Y: float = 2.95

    # Total speed can be up to 71
    # 71 = y + x
    # y = 71 / 3.35585
    # y = 21.16
    # 71 - 21.16 = 49.84 = x
    TARGET_SPEED_WIDE_X: float = 49.84
    TARGET_SPEED_WIDE_Y: float = 21.16

    DISTANCE_BETWEEN_IMAGES: int = 350  # How many pixel before taking another image

    ## [Melvin Task Planing]
    # Standard mapping, with no objectives and the camera angle below
    CURRENT_MELVIN_TASK: MELVINTask = MELVINTask.Mapping
    TARGET_CAMERA_ANGLE_ACQUISITION: CameraAngle = CameraAngle.Wide

    # Automatically do the next upcoming objective
    # CURRENT_MELVIN_TASK: MELVINTasks = MELVINTasks.Next_objective

    # Do a specific objective
    # CURRENT_MELVIN_TASK: MELVINTasks = MELVINTasks.Fixed_objective
    # FIXED_OBJECTIVE = "Aurora 10"

    # Go for the emergency beacon tracker
    # CURRENT_MELVIN_TASK: MELVINTask = MELVINTask.EBT

    # To set a custom time window to be active, or to disable all timing checks
    DO_TIMING_CHECK: bool = False
    START_TIME: datetime.datetime = datetime.datetime(
        2025, 1, 2, 12, 00, tzinfo=datetime.timezone.utc
    )
    STOP_TIME: datetime.datetime = datetime.datetime(
        2025, 1, 30, 12, 00, tzinfo=datetime.timezone.utc
    )

    DO_ACTUALLY_EXIT: bool = True

    OVERRIDES: dict[str, Any] = {}

    # load settings
    def load_settings(self) -> None:
        if not pathlib.Path(con.MEL_PERSISTENT_SETTINGS).exists():
            logger.debug("Settings don't exist")
            self.OVERRIDES = {}
        with open(con.MEL_PERSISTENT_SETTINGS, "r") as f:
            try:
                loaded = json.loads(f.read())
            except JSONDecodeError:
                logger.warning("Failed to load settings")
                self.OVERRIDES = {}
                return
            # logger.debug(f"{loaded=}")
            for key, value in loaded.items():
                self.OVERRIDES[key.upper()] = value
            # logger.debug(f"{self.OVERRIDES=}")

    # save settings
    def save_settings(self) -> None:
        with open(con.MEL_PERSISTENT_SETTINGS, "w") as f:
            f.write(json.dumps(self.OVERRIDES))

    # get settings
    def get_setting(self, key: str, default: Any = None) -> Any:
        return self.OVERRIDES.get(key.upper(), default)

    # set setting
    def set_setting(self, key: str, value: Any) -> None:
        # logger.debug(f"Setting {key.upper()} to {value}")
        # logger.debug(f"{self.OVERRIDES=}")
        self.OVERRIDES[key.upper()] = value
        # logger.debug(f"{self.OVERRIDES=}")
        self.save_settings()

    def set_settings(self, key_values: dict[str, Any]) -> None:
        # logger.debug(f"Setting {self.OVERRIDES}")
        if len(key_values.keys()) == 0:
            logger.debug("Clearing settings")
            self.set_setting("OVERRIDES", {})
        else:
            for key, value in key_values.items():
                self.set_setting(key, value)
        # logger.debug(f"Setting {self.OVERRIDES}")
        self.save_settings()

    def delete_settings(self, keys: list[str]) -> None:
        # logger.debug(f"Deleting {keys}")
        for key in keys:
            del self.OVERRIDES[key.upper()]
        # logger.debug(f"{self.OVERRIDES=}")
        self.save_settings()

    def init_settings(self) -> bool:
        if pathlib.Path(con.MEL_PERSISTENT_SETTINGS).exists():
            logger.debug("Settings already exist")
            return False
        logger.debug("Settings created")
        self.save_settings()
        return True

    # clear settings
    def clear_settings(self) -> None:
        self.OVERRIDES = None  # type: ignore
        # logger.debug(f"{self.OVERRIDES=}")

    def get_default_setting(self, key: str) -> Any:
        return super().__getattribute__(key)

    def __init__(self) -> None:
        super().__init__()
        if not self.init_settings():
            self.load_settings()

    def __getattribute__(self, item: str) -> Any:
        if item.startswith("__"):
            return super().__getattribute__(item)
        # logger.debug(f"Getting {item}")
        overrides = super().__getattribute__("OVERRIDES")
        if item.upper() in overrides:
            return overrides[item.upper()]
        return super().__getattribute__(item)

    def __setattr__(self, key: str, value: Any) -> None:
        # logger.debug(f"Setting {key} to {value}")
        if key == "OVERRIDES" and value is None:
            self.OVERRIDES.clear()
            self.save_settings()
        elif type(value) is dict:
            self.set_settings(value)
        else:
            self.set_setting(key.upper(), value)


settings = Settings()
