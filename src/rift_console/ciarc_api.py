import requests
import datetime

from enum import Enum
from loguru import logger

import shared.constants as con
from shared.models import State, CameraAngle, ZonedObjective, parse_objective_api
from rift_console.rift_console import RiftConsole

class HttpCode(Enum):
    GET = "get"
    PUT = "put"

# wrapper with error handling for ciarc api
def console_api(method: HttpCode, endpoint: str, params: dict = {}) -> dict:
    try:
        with requests.Session() as s:
            match method:
                case HttpCode.GET:
                    r = s.get(endpoint)
                case HttpCode.PUT:
                    r = s.put(endpoint, params=params)

    except requests.exceptions.ConnectionError:
        logger.error(f"Console: ConnectionError - possible no VPN?")
        return {}

    if r.status_code != 200:
        logger.warning(f"Console: could not contact satellite - {r.status_code} - {r.json()}.")
        return {}
    
    logger.debug(f"Console: received from API - {type(r.json())} - {r.json()}")
    return r.json()

def save_backup() -> datetime.datetime:
    console_api(method=HttpCode.GET, endpoint=con.BACKUP_ENDPOINT)
    t = datetime.datetime.now(datetime.timezone.utc).isoformat()
    logger.info(f"Console: saving satellite state.")
    
    return t

def load_backup(last_backup_date: datetime.datetime) -> None:
    console_api(method=HttpCode.PUT, endpoint=con.BACKUP_ENDPOINT)
    logger.info(f"Console: restoring satellite state from {last_backup_date}.")

    return

# WARNING, this disables network_simulation
def change_simulation_speed(user_speed_multiplier: int) -> None:
    params = {"is_network_simulation": "false", "user_speed_multiplier": str(user_speed_multiplier)}
    console_api(method=HttpCode.PUT, endpoint=con.SIMULATION_ENDPOINT, params=params)
    logger.info(f"Console: disabled network_sim - simulation speed changed set to {user_speed_multiplier}.")

    return

def set_network_sim(is_network_simulation: bool) -> None:
    user_speed_multiplier = console_api(method=HttpCode.GET, endpoint=con.OBSERVATION_ENDPOINT)["simulation_speed"]
    params = {"is_network_simulation": str(is_network_simulation).lower(), "user_speed_multiplier": str(user_speed_multiplier)}
    console_api(method=HttpCode.PUT, endpoint=con.SIMULATION_ENDPOINT, params=params)
    logger.info(f"Console: unchanged simulation speed of {user_speed_multiplier} - network sim set {is_network_simulation}.")

    return
