# shared imports
from shared.models import State, Telemetry, CameraAngle
from typing import Optional

import datetime


# not sure of ich das mit den Klassen so mag wie es jetzt ist TODO
class RiftTelemetry(Telemetry):
    fuel: float = 100.0
    battery: float = 100
    state: State = State.Unknown
    active_time: float = -1
    angle: CameraAngle = CameraAngle.Unknown

    width_x: int = -1
    height_y: int = -1
    vx: float = -1
    vy: float = -1

    target_vx: Optional[float] = None
    target_vy: Optional[float] = None
    simulation_speed: int = 1
    max_battery: float = 100

    old_pos: tuple[int, int] = (-1, -1)
    older_pos: tuple[int, int] = (-1, -1)
    oldest_pos: tuple[int, int] = (-1, -1)
    last_timestamp: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)
    pre_transition_state: State = State.Unknown
    planed_transition_state: State = State.Unknown

    # manually managed by drsAPI.change_simulation_speed()
    is_network_simulation_active: bool = True
    last_backup_time: Optional[datetime.datetime] = None

    # default value for creating a new folder to store images
    new_image_folder_name: str = "DATE_MISSING"
