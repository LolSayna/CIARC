# shared imports
from typing import Optional

import datetime


class RiftConsole:
    last_backup_date: Optional[datetime.datetime] = None
    is_network_simulation: Optional[bool] = None
    user_speed_multiplier: Optional[int] = None
