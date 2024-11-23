from loguru import logger
import requests  # type: ignore

import shared.constants as con

### ALL METHODS SO FAR ONLY WORK IF NETWORK SIMULATION IS DISABLED ###
# TODO file aufteilung von Riftconsole???


# /SIMULATION
def change_simulation_speed(user_speed_multiplier: int) -> None:
    params = {
        "is_network_simulation": "false",
        "user_speed_multiplier": str(user_speed_multiplier),
    }
    with requests.Session() as s:
        r = s.put(con.SIMULATION_ENDPOINT, params=params)
    if r.status_code == 200:
        logger.info(f"Changed simulation speed to {user_speed_multiplier}")
    else:
        logger.warning(f"Simulation Speed change to {user_speed_multiplier} failed")
        logger.debug(r)

    return
