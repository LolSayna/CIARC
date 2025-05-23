from typing import Any, Optional
import requests
import datetime

from loguru import logger

import shared.constants as con
from shared.models import (
    Achievement,
    BeaconObjective,
    CameraAngle,
    BaseTelemetry,
    State,
    Slot,
    ZonedObjective,
    live_utc,
    HttpCode,
)

def console_api(
    method: HttpCode,
    endpoint: str,
    params: dict[str, Any] = {},
    json: dict[str, Any] = {},
    files: dict[str, Any] = {},
) -> Any:
    """Wrapper for ciarc api with error handling."""
    try:
        with requests.Session() as s:
            match method:
                case HttpCode.GET:
                    r = s.get(endpoint, timeout=10)
                case HttpCode.PUT:
                    r = s.put(endpoint, params=params, json=json, timeout=5)
                case HttpCode.DELETE:
                    r = s.delete(endpoint, params=params, timeout=5)
                case HttpCode.POST:
                    r = s.post(endpoint, params=params, files=files)

    except requests.exceptions.ConnectionError:
        logger.error("Console: ConnectionError - possible no VPN?")
        return {}
    except requests.exceptions.ReadTimeout:
        logger.error("Console: Timeout error - possible no VPN?")
        return {}

    match r.status_code:
        case 200:
            logger.debug(f"Console: received from API - {type(r.json())} - {r.json()}")
            return r.json()
        case 405:
            # this happens with illegal request, for example GET instead of PUT
            logger.error(
                f"Console: API Not Allowed {r.status_code} - {type(r.json())} - {r.json()}"
            )
            return {}
        case 422:
            # this happens for an illegal control request, for example accelerating while not in acquisition
            logger.warning(
                f"Console: API Unprocessable Content- {r.status_code} - {type(r.json())} - {r.json()}."
            )
            return {}
        case 500:
            # this happens with an bug on the api side? Should not appear anymore
            logger.warning(
                f"Console: API File not found - {r.status_code} - {type(r.json())} - {r.json()}."
            )
            return {}
        case _:
            # unknow error?
            logger.warning(
                f"Console: could not contact satellite - {r.status_code} - {type(r.json())} - {r.json()}."
            )
            return {}


def console_api_image(angle: CameraAngle) -> Optional[str]:
    """Wrapper for CIARC API with images, since it has a slighly different syntax."""
    try:
        with requests.Session() as s:
            r = s.get(con.IMAGE_ENDPOINT, timeout=10)
    except requests.exceptions.ConnectionError:
        logger.error("Console: ConnectionError - possible no VPN?")
        return None
    except requests.exceptions.ReadTimeout:
        logger.error("Console: Timeout error - possible no VPN?")
        return None

    match r.status_code:
        case 200:
            img_timestamp = datetime.datetime.fromisoformat(
                r.headers.get("image-timestamp") or ""
            ).strftime("%Y-%m-%dT%H:%M:%S")
            with open(
                con.CONSOLE_LIVE_PATH + "live_" + angle + "_" + img_timestamp + ".png",
                "wb",
            ) as f:
                f.write(r.content)
            logger.warning(f"Console: received Image - {img_timestamp}")
            return img_timestamp
        case 400:
            logger.warning(f"Console: Bad request - {type(r.json())} - {r.json()}")
            return None
        case _:
            logger.warning(f"Console: Unkown error: - {type(r.json())} - {r}")
            return None


def reset() -> None:
    """Reset Simulation."""
    console_api(method=HttpCode.GET, endpoint=con.RESET_ENDPOINT)
    return

def save_backup() -> datetime.datetime:
    """Save backup of simulation."""
    console_api(method=HttpCode.GET, endpoint=con.BACKUP_ENDPOINT)
    t = live_utc()
    logger.info("Console: saving satellite state.")

    return t

def load_backup(last_backup_date: Optional[datetime.datetime]) -> None:
    """Load backup of simulation."""
    console_api(method=HttpCode.PUT, endpoint=con.BACKUP_ENDPOINT)
    logger.info(f"Console: restoring satellite state from {last_backup_date}.")

    return

def change_simulation_env(
    is_network_simulation: bool = False, user_speed_multiplier: int = 1
) -> None:
    """Change simspeed or network simulation."""
    params = {
        "is_network_simulation": str(is_network_simulation).lower(),
        "user_speed_multiplier": str(user_speed_multiplier),
    }
    console_api(method=HttpCode.PUT, endpoint=con.SIMULATION_ENDPOINT, params=params)
    logger.info(
        f"Console: simulation speed set to {user_speed_multiplier} - network simulation is {is_network_simulation}."
    )

    return


def update_api() -> (
    Optional[
        tuple[
            int,
            list[Slot],
            list[ZonedObjective],
            list[BeaconObjective],
            list[Achievement],
        ]
    ]
):
    """Pull status like slots and objectives, that are available even outside comms window."""
    s = console_api(method=HttpCode.GET, endpoint=con.SLOTS_ENDPOINT)
    o = console_api(method=HttpCode.GET, endpoint=con.OBJECTIVE_ENDPOINT)
    a = console_api(method=HttpCode.GET, endpoint=con.ACHIEVEMENTS_ENDPOINT)
    if s and o and a:
        (slots_used, slots) = Slot.parse_api(s)
        zoned_objectives = ZonedObjective.parse_api(o)
        beacon_objectives = BeaconObjective.parse_api(o)
        achievements = Achievement.parse_api(a)
        logger.info(
            f"Updated slots, objectives, achievments, used {slots_used} slots so far."
        )
        return (slots_used, slots, zoned_objectives, beacon_objectives, achievements)
    else:
        logger.warning("Could not update slots, objectives, achievments.")
        return None


def live_telemetry() -> Optional[BaseTelemetry]:
    """Pulls /observation."""
    d = console_api(method=HttpCode.GET, endpoint=con.OBSERVATION_ENDPOINT)
    if d:
        b = BaseTelemetry(**d)
        logger.info(f"Console: received live telemetry\n{b}.")
        return b
    else:
        logger.warning("Live telemtry failed.")
        return None


def change_angle(angle: CameraAngle) -> Any:
    """Change camera angle, keep veloctiy constant."""
    obs = console_api(method=HttpCode.GET, endpoint=con.OBSERVATION_ENDPOINT)
    if not obs:
        logger.warning("Console: no telemetry available, could not change camera angle")
        return {}
    json = {
        "vel_x": obs["vx"],
        "vel_y": obs["vy"],
        "camera_angle": angle,
        "state": obs["state"],
    }
    d = console_api(method=HttpCode.PUT, endpoint=con.CONTROL_ENDPOINT, json=json)

    if d and d["camera_angle"] == angle:
        logger.info(f"Console: angle changed to {d["camera_angle"]}.")
    else:
        logger.warning("Console: could not change angle, not in acquisition?")
        return {}

    return d


def change_state(state: State) -> Any:
    """Change State."""
    obs = console_api(method=HttpCode.GET, endpoint=con.OBSERVATION_ENDPOINT)
    if not obs:
        logger.warning("Console: no telemetry available, could not change camera angle")
        return
    json = {
        "vel_x": obs["vx"],
        "vel_y": obs["vy"],
        "camera_angle": obs["angle"],
        "state": state,
    }
    d = console_api(method=HttpCode.PUT, endpoint=con.CONTROL_ENDPOINT, json=json)

    if d and d["state"] == state:
        logger.info(f"Console: state changed to {d["state"]}.")
    else:
        logger.warning("Console: could not change state, not in acquisition?")
        return {}

    return d


def change_velocity(vel_x: float, vel_y: float) -> Any:
    """Change velocity of MELVIN."""
    obs = console_api(method=HttpCode.GET, endpoint=con.OBSERVATION_ENDPOINT)
    if not obs:
        logger.warning("Console: no telemetry available, could not change camera angle")
        return {}
    json = {
        "vel_x": vel_x,
        "vel_y": vel_y,
        "camera_angle": obs["angle"],
        "state": obs["state"],
    }
    d = console_api(method=HttpCode.PUT, endpoint=con.CONTROL_ENDPOINT, json=json)

    if d and d["vel_x"] == vel_x and d["vel_y"] == vel_y:
        logger.info(f"Console: velocity changed to ({d["vel_x"]},{d["vel_y"]}).")
        return d
    else:
        logger.warning("Console: could not change velocity, not in acquisition?")
        return {}


def book_slot(slot_id: int, enabled: bool) -> None:
    """Book coms slot."""
    params = {
        "slot_id": slot_id,
        "enabled": str(enabled).lower(),
    }
    d = console_api(method=HttpCode.PUT, endpoint=con.SLOTS_ENDPOINT, params=params)

    if d:
        if d["enabled"]:
            logger.info(f"Console: booked communication slot {d["id"]}.")
        else:
            logger.info(f"Console: cancled communication slot {d["id"]}")
    else:
        logger.warning("Console: could not book slot, not in acquisition?")


def delete_objective(id: int) -> None:
    """Delete objective (only used while testing)."""
    params = {
        "id": str(id),
    }
    d = console_api(
        method=HttpCode.DELETE, endpoint=con.OBJECTIVE_ENDPOINT, params=params
    )
    if d:
        logger.info(f"Console: removed objective with id - {id}.")
    else:
        logger.warning(f"Console: could not delete objective with id - {id}")


def add_modify_zoned_objective(
    id: int,
    name: str,
    start: datetime.datetime,
    end: datetime.datetime,
    zone: tuple[int, int, int, int],
    optic_required: CameraAngle,
    coverage_required: float,
    description: str,
    secret: bool,
) -> bool:
    """Add zoned or hidden objectives for testing."""
    json = {
        "zoned_objectives": [
            {
                "id": id,
                "name": name,
                "start": start.replace(tzinfo=datetime.timezone.utc).isoformat(),
                "end": end.replace(tzinfo=datetime.timezone.utc).isoformat(),
                "decrease_rate": 0.99,  # hardcoded since not in use
                "zone": [zone[0], zone[1], zone[2], zone[3]],
                "optic_required": optic_required,
                "coverage_required": coverage_required,
                "description": description,
                "sprite": "string",  # hardcoded since not in use
                "secret": secret,
            }
        ],
        "beacon_objectives": [],
    }

    d = console_api(method=HttpCode.PUT, endpoint=con.OBJECTIVE_ENDPOINT, json=json)

    if d:
        logger.info(f"Console: add/modifyed zoned objective {id}/{name}.")
        return True
    else:
        logger.warning(f"Console: could not add/modifyed zoned objective {id}/{name}")
        return False


def add_modify_ebt_objective(
    id: int,
    name: str,
    start: datetime.datetime,
    end: datetime.datetime,
    description: str,
    beacon_height: int,
    beacon_width: int,
) -> bool:
    """Add EBT objectives for testing."""
    json = {
        "zoned_objectives": [],
        "beacon_objectives": [
            {
                "id": id,
                "name": name,
                "start": start.replace(tzinfo=datetime.timezone.utc).isoformat(),
                "end": end.replace(tzinfo=datetime.timezone.utc).isoformat(),
                "decrease_rate": 0.99,  # hardcoded since not in use
                "description": description,
                "beacon_height": beacon_height,
                "beacon_width": beacon_width,
                "attempts_made": 0,  # did not change anything in API
            }
        ],
    }

    d = console_api(method=HttpCode.PUT, endpoint=con.OBJECTIVE_ENDPOINT, json=json)

    if d:
        logger.info(f"Console: add/modifyed ebt objective {id}/{name}.")
        return True
    else:
        logger.warning(f"Console: could not add/modifyed ebt objective {id}/{name}")
        return False


def send_beacon(beacon_id: int, height: int, width: int) -> Any:
    """Guess a EBT position."""
    params = {"beacon_id": beacon_id, "height": height, "width": width}
    d = console_api(method=HttpCode.PUT, endpoint=con.BEACON_ENDPOINT, params=params)
    if d:
        logger.info(f"Console: send_beacon - {d}.")
        return d
    else:
        logger.warning(f"Console: could not send_beacon - {id}")
        return {}


def upload_worldmap(image_path: str) -> Any:
    """Upload a worldmap"""
    files = {"image": (image_path, open(image_path, "rb"), "image/png")}
    d = console_api(method=HttpCode.POST, endpoint=con.DAILYMAP_ENDPOINT, files=files)
    if d:
        logger.info(f"Console: Uploaded world map - {d}.")
        # shutil.copyfile(
        #     image_path,
        #     "src/rift_console/static/media/"
        #     + live_utc().strftime("%d-%m-%Y")
        #     + "worldmap.png",
        # )
        return d
    else:
        logger.warning("Console: could not upload world map")
        return ""


def upload_objective(image_path: str, objective_id: int) -> Any:
    """Upload an images of an objective."""
    params = {
        "objective_id": objective_id,
    }
    files = {"image": (image_path, open(image_path, "rb"), "image/png")}
    d = console_api(
        method=HttpCode.POST, endpoint=con.IMAGE_ENDPOINT, params=params, files=files
    )
    if d:
        logger.info(f"Console: Uploaded objective - {d}.")
        # shutil.copyfile(
        #     image_path,
        #     con.CONSOLE_STICHED_PATH + str(objective_id) + "objective.png",
        # )
        return d
    else:
        logger.warning("Console: could not upload objective")
        return ""
