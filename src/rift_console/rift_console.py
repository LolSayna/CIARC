# shared imports
#from shared.models import State, Telemetry, CameraAngle, ZonedObjective
from typing import Optional

import datetime

from shared.models import BaseTelemetry


class RiftConsole:
    last_backup_date: Optional[datetime.datetime] = None
    is_network_simulation: Optional[bool] = None
    user_speed_multiplier: Optional[int] = None

    live_telemetry: Optional[BaseTelemetry] = None