from loguru import logger
import requests  # type: ignore

import shared.constants as con

### ALL METHODS SO FAR ONLY WORK IF NETWORK SIMULATION IS DISABLED ###
# TODO file aufteilung von Riftconsole???


# /SIMULATION
def change_simulation_speed -> None(
    melvin, is_network_simulation: bool = False, user_speed_multiplier: int = 1
) -> None:
    params = {
        "is_network_simulation": str(is_network_simulation).lower(),
        "user_speed_multiplier": str(user_speed_multiplier),
    }
    with requests.Session() as s:
        r = s.put(con.SIMULATION_ENDPOINT, params=params)
    if r.status_code == 200:
        logger.info(
            f"Changed simulation speed to {user_speed_multiplier} and is_network_simulation_active {is_network_simulation}"
        )

        # manually set flag, since it is not included in /OBSERVATION
        melvin.is_network_simulation_active = is_network_simulation
    else:
        logger.warning(
            f"Simulation Speed change to {user_speed_multiplier} and is_network_simulation_active {is_network_simulation}failed"
        )
        logger.debug(r)

    return


# /BACKUP get
def save_backup() -> None:
    with requests.Session() as s:
        r = s.get(con.BACKUP_ENDPOINT)
    if r.status_code == 200:
        logger.info("Saving system state")

        # TODO save last timestamp to see which State is currently saved
    else:
        logger.warning("Saving system state failed")
        logger.debug(r)

    return


# /BACKUP get
def load_backup() -> None:
    with requests.Session() as s:
        r = s.put(con.BACKUP_ENDPOINT)
    if r.status_code == 200:
        logger.info("Loading system state")
    else:
        logger.warning("Loading system state failed")
        logger.debug(r)

    return
