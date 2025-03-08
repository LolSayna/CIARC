from melvonaut import utils
import pytest
import pathlib
from melvonaut.settings import Settings
from shared import constants as con
import os


@pytest.fixture(scope="session", autouse=True)
def enable_logging():
    utils.setup_logging()


@pytest.fixture(scope="function", autouse=True)
def settings():
    if pathlib.Path(con.MEL_PERSISTENT_SETTINGS).exists():
        os.remove(con.MEL_PERSISTENT_SETTINGS)
    return Settings()
