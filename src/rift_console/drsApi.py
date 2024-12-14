from loguru import logger
import requests

import shared.constants as con

import datetime

from rift_console.RiftTelemetry import RiftTelemetry
from shared.models import State, CameraAngle

### ALL METHODS SO FAR ONLY WORK IF NETWORK SIMULATION IS DISABLED ###
# TODO file aufteilung von Riftconsole???


def reset(melvin: RiftTelemetry) -> None:
    with requests.Session() as s:
        r = s.get(con.RESET_ENDPOINT)

    if r.status_code == 200:
        logger.error("Relaunched Mevlin")
    else:
        logger.warning("Reset failed")
        logger.warning(r)


def update_telemetry(melvin: RiftTelemetry) -> None:
    # print("A")
    try:
        with requests.Session() as s:
            r = s.get(con.OBSERVATION_ENDPOINT)

    except requests.exceptions.ConnectionError:
        logger.error("HTTP Connection timed out, Network is unreachable.\n Is VPN activated?")
        exit()

    if r.status_code == 200:
        logger.debug("Observation successful")
    else:
        logger.warning("Observation failed")
        logger.warning(r)
        return

    data = r.json()

    # TODO check if data is valid
    # print(data)

    melvin.active_time = data["active_time"]
    melvin.battery = data["battery"]
    melvin.fuel = data["fuel"]
    melvin.state = data["state"]
    melvin.width_x = data["width_x"]
    melvin.height_y = data["height_y"]
    melvin.vx = data["vx"]
    melvin.vy = data["vy"]
    melvin.simulation_speed = data["simulation_speed"]
    melvin.timestamp = datetime.datetime.fromisoformat(data["timestamp"])
    melvin.angle = data["angle"]
    melvin.max_battery = data["max_battery"]
    melvin.new_image_folder_name = "Img_" + melvin.timestamp.strftime("%Y-%m-%dT%H:%M")

    if melvin.state != State.Acquisition:
        melvin.target_vx = melvin.vx
        melvin.target_vy = melvin.vy

    # if the last timestamp is longer then 10s ago shift around
    if (melvin.timestamp - melvin.last_timestamp).total_seconds() > 10:
        melvin.last_timestamp = melvin.timestamp
        melvin.oldest_pos = melvin.older_pos
        melvin.older_pos = melvin.old_pos
        melvin.old_pos = (melvin.width_x, melvin.height_y)

    # TODO fix bug with error state
    # if next state is safe mode, store last valid state
    # if melvin.state == State.Transition and melvin.state != State.Safe and data['state'] == State.Safe:
    #    melvin.pre_transition_state = melvin.state

    melvin.state = data["state"]

    if melvin.state != State.Transition:
        melvin.planed_transition_state = State.Unknown

    """
    print(melvin.timestamp)
    print(melvin.last_timestamp)
    print(melvin.old_pos)
    print(melvin.older_pos)
    print(melvin.oldest_pos)
    """

    return


# only change the state, nothing else
def control(
    melvin: RiftTelemetry,
    target_state: State,
    vel_x: float,
    vel_y: float,
    cameraAngle: CameraAngle,
) -> None:
    body = {
        "vel_x": vel_x,
        "vel_y": vel_y,
        "camera_angle": cameraAngle,
        "state": str(target_state),
    }

    melvin.pre_transition_state = melvin.state

    with requests.Session() as s:
        r = s.put(con.CONTROL_ENDPOINT, json=body)

    if r.status_code == 200:
        logger.info(
            f"Changing to: {target_state} w vx: {vel_x} vy: {vel_y} and camera: {cameraAngle}"
        )

    else:
        logger.warning("Control failed")
        logger.warning(r)
        return

    melvin.planed_transition_state = target_state
    return


# /SIMULATION
def change_simulation_speed(
    melvin: RiftTelemetry,
    is_network_simulation: bool = False,
    user_speed_multiplier: int = 1,
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
        logger.warning(r)

    return


# /BACKUP set
def save_backup(melvin: RiftTelemetry) -> None:
    with requests.Session() as s:
        r = s.get(con.BACKUP_ENDPOINT)
    if r.status_code == 200:
        # save last timestamp to see what is currently saved
        melvin.last_backup_time = datetime.datetime.now()

        logger.warning(f"Saving system state at {melvin.last_backup_time}")
    else:
        logger.warning("Saving system state failed")
        logger.warning(r)
    return


# /BACKUP get
def load_backup() -> None:
    with requests.Session() as s:
        r = s.put(con.BACKUP_ENDPOINT)
    if r.status_code == 200:
        logger.warning("Loading system state")
    else:
        logger.warning("Loading system state failed")
        logger.warning(r)

    return
