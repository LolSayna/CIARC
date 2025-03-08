import json
from melvonaut.settings import Settings
from shared import constants as con

from loguru import logger


def test_settings_init(settings):
    assert settings.OVERRIDES == {}
    with open(con.MEL_PERSISTENT_SETTINGS, "r") as f:
        assert json.loads(f.read()) == {}


def test_settings_load_settings(settings):
    settings.BATTERY_LOW_THRESHOLD = 10
    assert settings.OVERRIDES == {"BATTERY_LOW_THRESHOLD": 10}
    new_settings = Settings()
    assert new_settings.get_setting("BATTERY_LOW_THRESHOLD", 0) == 10, new_settings
    assert getattr(new_settings, "BATTERY_LOW_THRESHOLD") == 10, new_settings
    assert new_settings.BATTERY_LOW_THRESHOLD == 10, new_settings


def test_settings_save_settings(settings):
    settings.OVERRIDES = {"TEST": "VALUE"}
    settings.save_settings()
    with open(con.MEL_PERSISTENT_SETTINGS, "r") as f:
        assert json.loads(f.read()) == {"TEST": "VALUE"}


def test_settings_get_setting(settings):
    settings.OVERRIDES = {"TEST": "VALUE"}
    assert settings.get_setting("test", "DEFAULT") == "VALUE"
    assert settings.get_setting("nonexistent", "DEFAULT") == "DEFAULT"


def test_settings_set_setting(settings):
    settings.set_setting("test", "VALUE")
    assert settings.OVERRIDES == {"TEST": "VALUE"}
    with open(con.MEL_PERSISTENT_SETTINGS, "r") as f:
        assert json.loads(f.read()) == {"TEST": "VALUE"}


def test_settings_set_settings(settings):
    settings.set_settings({"test1": "value1", "test2": "value2"})
    assert settings.OVERRIDES == {"TEST1": "value1", "TEST2": "value2"}
    with open(con.MEL_PERSISTENT_SETTINGS, "r") as f:
        assert json.loads(f.read()) == {"TEST1": "value1", "TEST2": "value2"}


def test_settings_delete_settings(settings):
    settings.OVERRIDES = {"test1": "value1", "test2": "value2"}
    settings.delete_settings(["test1"])
    assert settings.OVERRIDES == {"TEST2": "value2"}
    with open(con.MEL_PERSISTENT_SETTINGS, "r") as f:
        assert json.loads(f.read()) == {"TEST2": "value2"}
    settings.BATTERY_LOW_THRESHOLD = 10
    settings.delete_settings(["BATTERY_LOW_THRESHOLD"])
    assert settings.BATTERY_LOW_THRESHOLD == 20


def test_settings_init_settings(settings):
    assert not settings.init_settings()


def test_settings_clear_settings(settings):
    settings.OVERRIDES = {"test1": "value1", "test2": "value2"}
    logger.debug(f"{settings=}")
    settings.BATTERY_LOW_THRESHOLD = 10
    logger.debug(f"{settings=}")
    settings.clear_settings()
    assert settings.OVERRIDES == {}
    logger.debug(f"{settings=}")
    with open(con.MEL_PERSISTENT_SETTINGS, "r") as f:
        assert json.loads(f.read()) == {}
    assert settings.BATTERY_LOW_THRESHOLD == 20, settings


def test_settings_getattr(settings):
    settings.OVERRIDES = {"TEST": "VALUE"}
    assert settings.TEST == "VALUE"


def test_settings_setattr(settings):
    settings.TEST = "VALUE"
    assert settings.OVERRIDES == {"TEST": "VALUE"}
    with open(con.MEL_PERSISTENT_SETTINGS, "r") as f:
        assert json.loads(f.read()) == {"TEST": "VALUE"}


def test_settings_load_invalid_json(settings):
    with open(con.MEL_PERSISTENT_SETTINGS, "w") as f:
        f.write("invalid json")
    new_settings = Settings()
    assert new_settings.OVERRIDES == {}


def test_settings_load_empty_json(settings):
    with open(con.MEL_PERSISTENT_SETTINGS, "w") as f:
        f.write("{}")
    new_settings = Settings()
    assert new_settings.OVERRIDES == {}


def test_get_default_setting(settings):
    settings.BATTERY_LOW_THRESHOLD = 10
    assert settings.get_default_setting("BATTERY_LOW_THRESHOLD") == 20
