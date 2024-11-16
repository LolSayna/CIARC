"""Test cases for the __main__ module."""
import asyncio
from time import sleep

import pytest
from click.testing import CliRunner
import uvloop

from melvonaut.__main__ import start_event_loop


@pytest.fixture
def runner() -> CliRunner:
    """Fixture for invoking command-line interfaces."""
    return CliRunner()


@pytest.mark.asyncio
def test_main_succeeds(runner: CliRunner) -> None:
    """It exits with a status code of zero."""

    import threading
    stop_event = threading.Event()
    thread = threading.Thread(target=start_event_loop, args=[stop_event], daemon=True)
    thread.start()

    sleep(5)
    stop_event.set()
    thread.join()
    assert thread.is_alive() == False
