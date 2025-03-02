import json

from aiohttp import web
import melvonaut.settings as settings
import melvonaut.persistent_settings as p_settings
from loguru import logger


# Download logs
async def download_logs(request: web.Request):
    pass


# Download telemetry
async def download_telemetry(request: web.Request):
    pass


# Download events
async def download_events(request: web.Request):
    pass


# Download images
async def download_images(request: web.Request):
    pass


# Set melvin task
async def set_melvin_task(request: web.Request):
    pass


# Reset settings
async def reset_settings(request: web.Request):
    logger.debug("Resetting settings")
    await p_settings.clear_settings()
    return web.Response(status=200, text="OK")


# Set setting
async def set_setting(request: web.Request):
    logger.debug("Setting settings")
    data = await request.json()
    logger.debug(f"Setting settings: {data}")
    await p_settings.set_settings(data)
    return web.Response(status=200, text="OK")


# Clear settings
async def clear_setting(request: web.Request):
    logger.debug("Clearing settings")
    data = await request.json()
    logger.debug(f"Clearing settings: {data}")
    await p_settings.delete_settings(data.keys())
    return web.Response(status=200, text="OK")


# Get setting
async def get_setting(request: web.Request):
    logger.debug("Getting settings")
    data = await request.json()
    logger.debug(f"Requested settings: {data}")
    response_settings = {}
    loaded_settings = await p_settings.load_settings()
    for key, value in data.items():
        response_settings[key] = loaded_settings.get(
            key, getattr(settings, key.upper())
        )
    return web.Response(status=200, text=json.dumps(response_settings))


async def get_all_settings(request: web.Request):
    logger.debug("Getting all settings")
    attrs = dir(settings)
    all_settings = {}
    for attr in attrs:
        all_settings[attr] = getattr(settings, attr)
    additional_settings = await p_settings.load_settings()
    for key, value in additional_settings.items():
        all_settings[key] = value
    return web.Response(status=200, text=json.dumps(all_settings))


# Add routes
def setup_routes(app) -> None:
    app.router.add_get("/api/download_logs", download_logs)
    app.router.add_get("/api/download_telemetry", download_telemetry)
    app.router.add_get("/api/download_events", download_events)
    app.router.add_get("/api/download_images", download_images)
    app.router.add_post("/api/set_melvin_task", set_melvin_task)
    app.router.add_get("/api/reset_settings", reset_settings)
    app.router.add_post("/api/set_setting", set_setting)
    app.router.add_post("/api/clear_setting", clear_setting)
    app.router.add_post("/api/get_setting", get_setting)
    app.router.add_get("/api/get_all_settings", get_all_settings)


async def run_api() -> None:
    logger.debug("Setting up API server")
    await p_settings.init_settings()
    app = web.Application()
    setup_routes(app)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.API_PORT)
    try:
        logger.info(f"API server started on port {settings.API_PORT}")
        await site.start()
        logger.debug("API server started")
    finally:
        logger.debug("Shutting down API server")
        await runner.cleanup()
