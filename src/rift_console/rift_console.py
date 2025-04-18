import datetime
from typing import Optional

from rift_console.melvin_api import MelvonautTelemetry
import shared.constants as con
from shared.models import (
    Achievement,
    BaseTelemetry,
    BeaconObjective,
    Event,
    Slot,
    State,
    ZonedObjective,
)


class RiftConsole:
    """State of a currently running Console, including live data from CIARC/Melvonaut API."""

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
    completed_ids: list[int] = []
    achievements: list[Achievement] = []
    past_traj: list[tuple[int, int]] = []
    future_traj: list[tuple[int, int]] = []
    live_melvonaut_api: Optional[MelvonautTelemetry] = None
    melvonaut_image_count: int = -1  # -1 indicates no data
    console_image_count: int = -1  # -1 indicates no data
    console_image_dates: list[tuple[str, int]] = []
    ebt_ping_list: list[tuple[int, int]] = []
    console_found_events: list[Event] = []
    melvin_task: str = ""
    melvin_lens: str = ""

    def get_draw_zoned_obj(self) -> list[dict[str, object]]:
        """Picks objectives to be drawn later from its telemetry."""
        get_draw_zoned_obj = []
        for obj in self.zoned_objectives:
            if obj.zone is not None:
                draw = {
                    "name": obj.id,
                    "zone": [
                        int(obj.zone[0]),
                        int(obj.zone[1]),
                        int(obj.zone[2]),
                        int(obj.zone[3]),
                    ],
                }
                get_draw_zoned_obj.append(draw)
                if len(get_draw_zoned_obj) >= 5:  # only collect 5 for visual clarity
                    break
        return get_draw_zoned_obj

    def predict_trajektorie(
        self,
    ) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        """Calculate the points that melvin goes through next"""
        past = []
        future = []

        if self.live_telemetry:
            for i in range(0, con.TRAJ_TIME, con.TRAJ_STEP):
                (x, y) = RiftConsole.fix_overflow(
                    int(self.live_telemetry.width_x + self.live_telemetry.vx * i),
                    int(self.live_telemetry.height_y + self.live_telemetry.vy * i),
                )
                future.append((x, y))
                (x, y) = RiftConsole.fix_overflow(
                    int(self.live_telemetry.width_x - self.live_telemetry.vx * i),
                    int(self.live_telemetry.height_y - self.live_telemetry.vy * i),
                )
                past.append((x, y))

        return (past, future)

    @staticmethod
    def fix_overflow(x: int, y: int) -> tuple[int, int]:
        """Helper for trajektorie predition. Does "teleportation" when MELVIN reaches one side of the map."""
        if x > con.WORLD_X:
            x = x % con.WORLD_X

        while x < 0:
            x += con.WORLD_X

        if y > con.WORLD_Y:
            y = y % con.WORLD_Y
        while y < 0:
            y += con.WORLD_Y

        return (x, y)
