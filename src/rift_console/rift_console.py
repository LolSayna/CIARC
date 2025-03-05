# shared imports
from typing import Optional

import datetime

from shared.models import Achievement, BaseTelemetry, BeaconObjective, Slot, State, ZonedObjective


class RiftConsole:
    last_backup_date: Optional[datetime.datetime] = None
    is_network_simulation: Optional[bool] = None
    user_speed_multiplier: Optional[int] = None

    live_telemetry: Optional[BaseTelemetry] = None
    prev_state: State = State.Unknown
    next_state: State = State.Unknown
    slots_used: Optional[int] = None
    slots: list[Slot] = []
    zoned_objectives: list[ZonedObjective] = []
    beacon_objectives: list[BeaconObjective] = []
    achievements: list[Achievement] = []
