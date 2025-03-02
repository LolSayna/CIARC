
from aiofile import async_open
import json
import pathlib
from loguru import logger
from shared import constants as con


# load settings
async def load_settings() -> dict:
    async with async_open(con.MEL_PERSISTENT_SETTINGS, "r") as afp:
        return json.loads(await afp.read())


# save settings
async def save_settings(settings):
    async with async_open(con.MEL_PERSISTENT_SETTINGS, "w") as afp:
        await afp.write(json.dumps(settings))


# get settings
async def get_setting(key, default):
    settings = await load_settings()
    return settings.get(key, default)


# set setting
async def set_setting(key, value):
    settings = await load_settings()
    settings[key] = value
    await save_settings(settings)


async def set_settings(key_values: dict):
    settings = await load_settings()
    for key, value in key_values.items():
        settings[key] = value
    await save_settings(settings)


async def delete_settings(keys: list):
    settings = await load_settings()
    for key in keys:
        del settings[key]
    await save_settings(settings)


async def init_settings():
    if pathlib.Path(con.MEL_PERSISTENT_SETTINGS).exists():
        logger.debug("Settings already exist")
        return
    await save_settings({})
    logger.debug("Settings created")


# clear settings
async def clear_settings():
    await save_settings({})
