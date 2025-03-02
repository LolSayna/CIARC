from aiofile import async_open
import json


# load settings
async def load_settings() -> dict:
    async with async_open("persistent_settings.json", "r") as afp:
        return json.loads(await afp.read())


# save settings
async def save_settings(settings):
    async with async_open("persistent_settings.json", "w") as afp:
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


# clear settings
async def clear_settings():
    await save_settings({})
