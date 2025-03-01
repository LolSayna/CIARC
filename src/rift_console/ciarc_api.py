import requests
import datetime

from enum import Enum
from loguru import logger

import shared.constants as con
from shared.models import State, CameraAngle, ZonedObjective, parse_objective_api, BaseTelemetry
from rift_console.rift_console import RiftConsole

class HttpCode(Enum):
    GET = "get"
    PUT = "put"

# wrapper with error handling for ciarc api
def console_api(method: HttpCode, endpoint: str, params: dict = {}, json: dict = {}) -> dict:
    try:
        with requests.Session() as s:
            match method:
                case HttpCode.GET:
                    r = s.get(endpoint)
                case HttpCode.PUT:
                    r = s.put(endpoint, params=params, json=json)

    except requests.exceptions.ConnectionError:
        logger.error(f"Console: ConnectionError - possible no VPN?")
        return {}

    match r.status_code:
        case 200:
            logger.debug(f"Console: received from API - {type(r.json())} - {r.json()}")
            return r.json()
        case 405:
            # this happens with illegal request, for example GET instead of PUT
            logger.error(f"Console: API Not Allowed {r.status_code} - {type(r.json())} - {r.json()}")
            return {}
        case 422:
            # this happens for an illegal control request, for example accelerating while not in acquisition
            logger.warning(f"Console: API Unprocessable Content- {r.status_code} - {type(r.json())} - {r.json()}.")
            return {}
        case _:
            # unknow error?
            logger.warning(f"Console: could not contact satellite - {r.status_code} - {type(r.json())} - {r.json()}.")
            return {}
    

def save_backup() -> datetime.datetime:
    console_api(method=HttpCode.GET, endpoint=con.BACKUP_ENDPOINT)
    t = datetime.datetime.now(datetime.timezone.utc).isoformat()
    logger.info(f"Console: saving satellite state.")
    
    return t

def load_backup(last_backup_date: datetime.datetime) -> None:
    console_api(method=HttpCode.PUT, endpoint=con.BACKUP_ENDPOINT)
    logger.info(f"Console: restoring satellite state from {last_backup_date}.")

    return

# WARNING, this disables network_simulation, since we dont know if it was enabled before
def change_simulation_speed(user_speed_multiplier: int) -> None:
    params = {"is_network_simulation": "false", "user_speed_multiplier": str(user_speed_multiplier)}
    console_api(method=HttpCode.PUT, endpoint=con.SIMULATION_ENDPOINT, params=params)
    logger.info(f"Console: disabled network_sim - simulation speed changed set to {user_speed_multiplier}.")

    return

def change_network_sim(is_network_simulation: bool, old_user_speed_multiplier: int = 1) -> None:
    params = {"is_network_simulation": str(is_network_simulation).lower(), "user_speed_multiplier": str(old_user_speed_multiplier)}
    console_api(method=HttpCode.PUT, endpoint=con.SIMULATION_ENDPOINT, params=params)
    logger.info(f"Console: simulation speed is {old_user_speed_multiplier} - network sim set {is_network_simulation}.")

    return

def live_observation() -> BaseTelemetry:
    d = console_api(method=HttpCode.GET, endpoint=con.OBSERVATION_ENDPOINT)
    b = BaseTelemetry(**d)
    logger.info(f"Console: received live telemetry\n{b}.")

    return b


def change_velocity(vel_x: float, vel_y: float) -> dict:
    obs = console_api(method=HttpCode.GET, endpoint=con.OBSERVATION_ENDPOINT)
    if not obs:
        logger.warning(f"Console: no telemetry available, could not change velocity")
        return
    json = {"vel_x" : vel_x, "vel_y": vel_y, "camera_angle": obs["angle"], "state": obs["state"]}
    logger.error(json)
    d = console_api(method=HttpCode.PUT, endpoint=con.CONTROL_ENDPOINT, json=json)
    
    if d:
        logger.info(f"Console: changed velocity to ({d["vel_x"],d["vel_y"]}).")
    else:
        logger.warning(f"Console: could not change velocity, not in acquisition?")

    return d


def change_state(angle: CameraAngle) -> dict:
    obs = console_api(method=HttpCode.GET, endpoint=con.OBSERVATION_ENDPOINT)
    if not obs:
        logger.warning(f"Console: no telemetry available, could not change camera angle")
        return
    json = {"vel_x" : obs["vx"], "vel_y": obs["vy"], "camera_angle": angle, "state": obs["state"]}
    d = console_api(method=HttpCode.PUT, endpoint=con.CONTROL_ENDPOINT, json=json)
    
    if d and d["camera_angle"] == angle:
        logger.info(f"Console: angle changed to {d["camera_angle"]}.")
    else:
        logger.warning(f"Console: could not change angle, not in acquisition?")

    return d
