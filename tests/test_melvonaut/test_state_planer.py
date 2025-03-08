import pytest
from melvonaut import state_planer


@pytest.fixture
def sp():
    sp = state_planer.StatePlanner()
    return sp


def test_state_planer(sp):
    assert isinstance(sp, state_planer.StatePlanner)
    assert isinstance(state_planer.state_planner, state_planer.StatePlanner)
