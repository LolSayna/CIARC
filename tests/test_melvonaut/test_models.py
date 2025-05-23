import pytest
from shared.models import Event
import pathlib
from shared import constants as con
import datetime


event = Event(
    event="test-event",
    id=123456,
    timestamp=datetime.datetime.now(),
    current_x=0.0,
    current_y=0.0,
)


@pytest.fixture
@pytest.mark.asyncio
async def initialize_events():
    events_file = pathlib.Path(con.EVENT_LOCATION_CSV)
    if events_file.exists():
        events_file.unlink()
    await event.to_csv()


def test_load_events_from_csv(initialize_events):
    events = Event.load_events_from_csv(path=con.EVENT_LOCATION_CSV)
    assert len(events) > 0
    assert isinstance(events[0], Event)
