import requests
import datetime

from enum import Enum
from loguru import logger

import shared.constants as con
from shared.models import (
    Achievement,
    BeaconObjective,
    BeaconObjective,
    CameraAngle,
    BaseTelemetry,
    State,
    Slot,
    ZonedObjective
)


class HttpCode(Enum):
    GET = "get"
    PUT = "put"
    DELETE = "delete"


# wrapper with error handling for ciarc api
def console_api(
    method: HttpCode, endpoint: str, params: dict = {}, json: dict = {}
) -> dict:
    try:
        with requests.Session() as s:
            match method:
                case HttpCode.GET:
                    r = s.get(endpoint)
                case HttpCode.PUT:
                    r = s.put(endpoint, params=params, json=json)
                case HttpCode.DELETE:
                    r = s.delete(endpoint, params=params)

    except requests.exceptions.ConnectionError:
        logger.error("Console: ConnectionError - possible no VPN?")
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
        case _:
            # unknow error?
            logger.warning(
                f"Console: could not contact satellite - {r.status_code} - {type(r.json())} - {r.json()}."
            )
            return {}


def reset() -> None:
    console_api(method=HttpCode.GET, endpoint=con.RESET_ENDPOINT)
    return


def save_backup() -> datetime.datetime:
    console_api(method=HttpCode.GET, endpoint=con.BACKUP_ENDPOINT)
    t = datetime.datetime.now(datetime.timezone.utc).isoformat()
    logger.info("Console: saving satellite state.")

    return t


def load_backup(last_backup_date: datetime.datetime) -> None:
    console_api(method=HttpCode.PUT, endpoint=con.BACKUP_ENDPOINT)
    logger.info(f"Console: restoring satellite state from {last_backup_date}.")

    return


def change_simulation_env(
    is_network_simulation: bool = False, user_speed_multiplier: int = 1
) -> None:
    params = {
        "is_network_simulation": str(is_network_simulation).lower(),
        "user_speed_multiplier": str(user_speed_multiplier),
    }
    console_api(method=HttpCode.PUT, endpoint=con.SIMULATION_ENDPOINT, params=params)
    logger.info(
        f"Console: simulation speed set to {user_speed_multiplier} - network simulation is {is_network_simulation}."
    )

    return


def live_observation() -> BaseTelemetry:
    d = console_api(method=HttpCode.GET, endpoint=con.OBSERVATION_ENDPOINT)
    s = console_api(method=HttpCode.GET, endpoint=con.SLOTS_ENDPOINT)
    o = console_api(method=HttpCode.GET, endpoint=con.OBJECTIVE_ENDPOINT)
    a = console_api(method=HttpCode.GET, endpoint=con.ACHIEVEMENTS_ENDPOINT)
    if d and s and o and a:
        b = BaseTelemetry(**d)
        (slots_used, slots) = Slot.parse_api(s)
        zoned_objectives = ZonedObjective.parse_api(o)
        beacon_objectives = BeaconObjective.parse_api(o)
        achievements = Achievement.parse_api(a)
        logger.info(f"Console: received live telemetry\n{b}.")
        return (b, slots_used, slots, zoned_objectives, beacon_objectives, achievements)
    else:
        logger.warning("Live telemtry failed.")
        return None


def change_velocity(vel_x: float, vel_y: float) -> dict:
    obs = console_api(method=HttpCode.GET, endpoint=con.OBSERVATION_ENDPOINT)
    if not obs:
        logger.warning("Console: no telemetry available, could not change velocity")
        return
    json = {
        "vel_x": vel_x,
        "vel_y": vel_y,
        "camera_angle": obs["angle"],
        "state": obs["state"],
    }
    logger.error(json)
    d = console_api(method=HttpCode.PUT, endpoint=con.CONTROL_ENDPOINT, json=json)

    if d:
        logger.info(f"Console: changed velocity to ({d["vel_x"],d["vel_y"]}).")
    else:
        logger.warning("Console: could not change velocity, not in acquisition?")

    return d


def change_angle(angle: CameraAngle) -> dict:
    obs = console_api(method=HttpCode.GET, endpoint=con.OBSERVATION_ENDPOINT)
    if not obs:
        logger.warning("Console: no telemetry available, could not change camera angle")
        return
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


def change_state(state: State) -> dict:
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


def change_velocity(vel_x: float, vel_y: float) -> dict:
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


def book_slot(slot_id: int, enabled: bool):
    params = {
        "slot_id": slot_id,
        "enabled": str(enabled).lower(),
    }
    d = console_api(method=HttpCode.PUT, endpoint=con.SLOTS_ENDPOINT, params=params)

    if d:
        if d["enabled"]:
            logger.info(f"Console: booked communication slot ({d["id"]}.")
        else:
            logger.info(f"Console: cancled communication slot {d["id"]}")
        return d
    else:
        logger.warning("Console: could not book slot, not in acquisition?")
        return {}

def delete_objective(id: int):
    params = {
        "id": str(id),
    }
    d = console_api(method=HttpCode.DELETE, endpoint=con.OBJECTIVE_ENDPOINT, params=params)
    if d:
        logger.info(f"Console: removed objective with id - {id}.")
    else:
        logger.warning(f"Console: could not delete objective with id - {id}")