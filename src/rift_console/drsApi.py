from loguru import logger
import requests

import shared.constants as con

import datetime

from rift_console.rift_telemetry import RiftTelemetry
from shared.models import State, CameraAngle, ZonedObjective

### ALL METHODS SO FAR ONLY WORK IF NETWORK SIMULATION IS DISABLED ###
# TODO file aufteilung von Riftconsole???


def fixOverflow(x: int, y: int) -> tuple[int, int]:
    if x > con.WORLD_X:
        x = x % con.WORLD_X
    elif x < 0:
        x += con.WORLD_X

    if y > con.WORLD_Y:
        y = y % con.WORLD_Y
    elif y < 0:
        y += con.WORLD_Y
    return (x, y)


count = 3600
step = 1 / 10


def predictTrajektorie(
    x: int, y: int, vx: float, vy: float, simulation_speed: int, reverse: bool = False
) -> list[tuple[int, int]]:
    """Calculate the points that melvin goes through next"""
    traj = []

    if reverse:
        vx = -vx
        vy = -vy

    # Subpoints, to get more smooth points make it higher
    step_multiplicator = 1
    # TODO

    for _ in range(int(step_multiplicator * con.TRAJ_TIME / simulation_speed)):
        (x, y) = fixOverflow(
            x + vx * simulation_speed * step_multiplicator,
            y + vy * simulation_speed * step_multiplicator,
        )
        traj.append((x, y))

    return traj


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
            objective_list = s.get(con.OBJECTIVE_ENDPOINT)

    except requests.exceptions.ConnectionError:
        logger.error(
            "HTTP Connection timed out, Network is unreachable.\n Is VPN activated?"
        )
        exit()

    if r.status_code == 200 and objective_list.status_code == 200:
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

    # TODO fix bug with error state
    # if next state is safe mode, store last valid state
    # if melvin.state == State.Transition and melvin.state != State.Safe and data['state'] == State.Safe:
    #    melvin.pre_transition_state = melvin.state

    melvin.state = data["state"]

    if melvin.state != State.Transition:
        melvin.planed_transition_state = State.Unknown

    melvin.z_obj_list = ZonedObjective.parse_api(objective_list.json())

    melvin.drawnObjectives = []
    for obj in melvin.z_obj_list:
        if obj.zone is not None:
            draw = {
                "name": obj.name,
                "start": obj.start.isoformat()[:-3],
                "end": obj.end.isoformat()[:-3],
                "zone": [
                    int(obj.zone[0] / con.SCALING_FACTOR),
                    int(obj.zone[1] / con.SCALING_FACTOR),
                    int(obj.zone[2] / con.SCALING_FACTOR),
                    int(obj.zone[3] / con.SCALING_FACTOR),
                ],
            }
            melvin.drawnObjectives.append(draw)
            if len(melvin.drawnObjectives) >= 5:
                break

    melvin.predTraj = predictTrajektorie(
        melvin.width_x, melvin.height_y, melvin.vx, melvin.vy, melvin.simulation_speed
    )
    melvin.pastTraj = predictTrajektorie(
        melvin.width_x,
        melvin.height_y,
        melvin.vx,
        melvin.vy,
        melvin.simulation_speed,
        reverse=True,
    )
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
