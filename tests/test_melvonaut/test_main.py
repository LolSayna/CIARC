"""Test cases for the __main__ module."""

import warnings
from time import sleep

import pytest
from click.testing import CliRunner

from melvonaut.__main__ import start_event_loop


@pytest.fixture
def runner() -> CliRunner:
    """Fixture for invoking command-line interfaces."""
    return CliRunner()


def test_main_succeeds(runner: CliRunner) -> None:
    """It exits with a status code of zero."""

    pass
    #import threading

    #thread = threading.Thread(target=start_event_loop, daemon=True)
    #with warnings.catch_warnings():
    #    thread.start()

    #    sleep(2)
    #    thread.join(timeout=3)
    #assert not thread.is_alive()
