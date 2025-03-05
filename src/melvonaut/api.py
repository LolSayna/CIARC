import importlib.metadata
import psutil
from aiohttp import web
from io import StringIO, BytesIO
import melvonaut.settings as settings
import melvonaut.persistent_settings as p_settings
from shared import constants as con
from loguru import logger
import asyncio
import pathlib
import shared.models as models
import datetime
from melvonaut.settings import setup_file_logging


async def health(request: web.Request):
    return web.Response(status=200, text="OK")


async def get_disk_usage(request: web.Request):
    logger.debug("Getting disk usage")
    disk_root = psutil.disk_usage("/")
    disk_home = psutil.disk_usage("/home")
    return web.json_response(
        {"root": disk_root._asdict(), "home": disk_home._asdict()}, status=200
    )


async def get_memory_usage(request: web.Request):
    logger.debug("Getting memory usage")
    memory_usage = psutil.virtual_memory()
    return web.json_response(memory_usage._asdict(), status=200)


async def get_cpu_usage(request: web.Request):
    logger.debug("Getting CPU usage")
    cpu_usage = psutil.cpu_times()
    cpu_percent = psutil.cpu_percent()
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()
    cpu = {
        "user": cpu_usage.user,
        "system": cpu_usage.system,
        "idle": cpu_usage.idle,
        "percent": cpu_percent,
        "physical_cores": cpu_count,
        "current_freq": cpu_freq.current,
        "max_freq": cpu_freq.max,
        "min_freq": cpu_freq.min,
    }
    return web.json_response(cpu, status=200)


async def get_restart_melvin(request: web.Request):
    return web.Response(status=501, text="Not Implemented")


async def get_shutdown_melvin(request: web.Request):
    try:
        return web.Response(status=200, text="OK")
    finally:
        if settings.DO_ACTUALLY_EXIT:
            loop = asyncio.get_running_loop()
            loop.stop()
            pending_tasks = asyncio.all_tasks()
            for task in pending_tasks:
                task.cancel()
            exit()
        else:
            logger.warning("Requested shutdown, but not actually exiting")


async def post_execute_command(request: web.Request):
    data = await request.json()
    cmd = data.get("cmd")
    logger.debug(f"Executing command: {cmd}")
    output = []
    try:
        process = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            output.append(line.decode())
        await process.wait()
        return_code = process.returncode
        logger.debug(f"Command output: {output}")
        return web.json_response(
            {"output": output, "return_code": return_code}, status=200
        )
    except asyncio.TimeoutError:
        return web.json_response({"output": output, "error": "Timeout"}, status=500)
    except asyncio.CancelledError:
        return web.json_response({"output": output, "error": "Cancelled"}, status=500)
    except Exception as e:
        return web.json_response({"output": output, "error": str(e)}, status=500)


async def get_melvin_version(request: web.Request):
    return web.json_response(
        {"version": importlib.metadata.version("ciarc")}, status=200
    )


async def get_list_log_files(request: web.Request):
    logger.debug("Listing log files")
    log_files = []
    folder = pathlib.Path(con.MEL_LOG_PATH)
    try:
        for file in folder.iterdir():
            if not file.is_file():
                continue
            if not file.name.endswith(".log"):
                continue
            log_files.append(file.name)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)
    return web.json_response({"log_files": log_files}, status=200)


async def post_download_log(request: web.Request):
    data = await request.json()
    logger.debug(f"Downloading log: {data}")
    log_file = pathlib.Path(con.MEL_LOG_PATH) / data.get("file")
    if log_file.exists():
        return web.FileResponse(log_file, status=200)
    else:
        return web.Response(status=404, text="File not found")


async def post_download_log_and_clear(request: web.Request):
    data = await request.json()
    logger.debug(f"Downloading log and clearing: {data}")
    log_file = pathlib.Path(con.MEL_LOG_PATH) / data.get("file")
    if log_file.exists():
        log_file_content = StringIO(log_file.read_text())
        try:
            return web.Response(body=log_file_content, status=200)
        finally:
            log_file.unlink()
            setup_file_logging()
    else:
        return web.Response(status=404, text="File not found")


async def post_clear_log(request: web.Request):
    data = await request.json()
    logger.debug(f"Clearing log: {data}")
    log_file = pathlib.Path(con.MEL_LOG_PATH) / data.get("file")
    if log_file.exists():
        if log_file.is_dir():
            return web.Response(status=400, text=f"{log_file} is a directory")
        if not log_file.name.endswith(".log"):
            return web.Response(status=400, text=f"{log_file} is not a log file")
        log_file.unlink()
        setup_file_logging()
        return web.Response(status=200, text=f"{log_file} cleared")
    else:
        return web.Response(status=404, text=f"{log_file} not found")


async def get_clear_all_logs(request: web.Request):
    try:
        logger.debug("Clearing all log files")
        log_files = []
        folder = pathlib.Path(con.MEL_LOG_PATH)
        for file in folder.iterdir():
            if file.is_dir():
                continue
            if not file.name.endswith(".log"):
                continue
            log_files.append(file.name)
            file.unlink()
        setup_file_logging()
        return web.json_response({"Cleared_files": log_files}, status=200)
    except Exception as e:
        logger.exception(e)
        return web.json_response({"error": str(e)}, status=500)


# Download telemetry
async def get_download_telemetry(request: web.Request):
    logger.debug("Downloading telemetry")
    telemetry_file = pathlib.Path(con.TELEMETRY_LOCATION_CSV)
    if telemetry_file.exists():
        return web.FileResponse(telemetry_file, status=200)
    else:
        return web.Response(status=404, text="File not found")


async def get_download_telemetry_and_clear(request: web.Request):
    logger.debug("Downloading telemetry and clearing")
    telemetry_file = pathlib.Path(con.TELEMETRY_LOCATION_CSV)
    if telemetry_file.exists():
        telemetry_file_content = StringIO(telemetry_file.read_text())
        try:
            return web.Response(body=telemetry_file_content, status=200)
        finally:
            telemetry_file.unlink()
    else:
        return web.Response(status=404, text="File not found")


async def get_clear_telemetry(request: web.Request):
    logger.debug("Clearing telemetry")
    telemetry_file = pathlib.Path(con.TELEMETRY_LOCATION_CSV)
    if telemetry_file.exists():
        telemetry_file.unlink()
        return web.Response(status=200, text="OK")
    else:
        return web.Response(status=404, text="File not found")


# Download events
async def get_download_events(request: web.Request):
    logger.debug("Downloading events")
    events_file = pathlib.Path(con.EVENT_LOCATION_CSV)
    if events_file.exists():
        return web.FileResponse(events_file, status=200)
    else:
        return web.Response(status=404, text="File not found")


async def get_download_events_and_clear(request: web.Request):
    logger.debug("Downloading events and clearing")
    events_file = pathlib.Path(con.EVENT_LOCATION_CSV)
    if events_file.exists():
        events_file_content = StringIO(events_file.read_text())
        try:
            return web.Response(body=events_file_content, status=200)
        finally:
            events_file.unlink()
    else:
        return web.Response(status=404, text="File not found")


async def get_clear_events(request: web.Request):
    logger.debug("Clearing events")
    events_file = pathlib.Path(con.EVENT_LOCATION_CSV)
    if events_file.exists():
        events_file.unlink()
        return web.Response(status=200, text="OK")
    else:
        return web.Response(status=404, text="File not found")


async def get_list_images(request: web.Request):
    logger.debug("Listing images")
    folder = pathlib.Path(con.IMAGE_PATH_BASE)
    if not folder.exists():
        return web.Response(status=404, text=f"Folder not found: {folder}")
    images = [str(file.name) for file in folder.rglob("*.png") if file.is_file()]
    return web.json_response({"images": images}, status=200)


async def post_download_image(request: web.Request):
    data = await request.json()
    logger.debug(f"Downloading image: {data}")
    image_file = pathlib.Path(con.IMAGE_PATH_BASE) / data.get("file")
    if image_file.exists():
        return web.FileResponse(image_file, status=200)
    else:
        return web.Response(status=404, text="File not found")


async def post_download_image_and_clear(request: web.Request):
    data = await request.json()
    logger.debug(f"Downloading image and clearing: {data}")
    image_file = pathlib.Path(con.IMAGE_PATH_BASE) / data.get("file")
    if image_file.exists():
        image_file_content = BytesIO(image_file.read_bytes())
        try:
            return web.Response(body=image_file_content, status=200)
        finally:
            image_file.unlink()
    else:
        return web.Response(status=404, text="File not found")


async def get_clear_all_images(request: web.Request):
    logger.debug("Clearing all images")
    folder = pathlib.Path(con.IMAGE_PATH_BASE)
    images = [str(file) for file in folder.rglob("*.png") if file.is_file()]
    for image in images:
        pathlib.Path(image).unlink()
    return web.Response(status=200, text="OK")


async def post_set_melvin_task(request: web.Request):
    data = await request.json()
    logger.debug(f"Setting melvin task: {data}")
    task = data.get("task", None)
    if not task:
        logger.warning("Missing field task")
        return web.Response(status=400, text="Missing field task")
    try:
        melvin_task = models.MELVINTask(task)
    except ValueError:
        logger.warning("Invalid task")
        return web.Response(status=400, text="Invalid task")
    except Exception as e:
        logger.warning(f"Error setting melvin task: {e}")
        return web.Response(status=500, text=str(e))
    await p_settings.set_settings({"CURRENT_MELVIN_TASK": melvin_task})
    return web.Response(status=200, text="OK")


async def get_reset_settings(request: web.Request):
    logger.debug("Resetting settings")
    await p_settings.clear_settings()
    return web.Response(status=200, text="OK")


async def post_set_setting(request: web.Request):
    logger.debug("Setting settings")
    data = await request.json()
    logger.debug(f"Setting settings: {data}")
    await p_settings.set_settings(data)
    return web.Response(status=200, text="OK")


async def post_clear_setting(request: web.Request):
    logger.debug("Clearing settings")
    data = await request.json()
    logger.debug(f"Clearing settings: {data}")
    await p_settings.delete_settings(data.keys())
    return web.Response(status=200, text="OK")


async def post_get_setting(request: web.Request):
    logger.debug("Getting settings")
    data = await request.json()
    logger.debug(f"Requested settings: {data}")
    response_settings = {}
    loaded_settings = await p_settings.load_settings()
    for key, value in data.items():
        try:
            response_settings[key] = loaded_settings.get(
                key, getattr(settings, key.upper())
            )
        except AttributeError:
            return web.Response(status=404, text=f"Setting not found: {key}")
    return web.json_response(response_settings, status=200)


async def get_all_settings(request: web.Request):
    logger.debug("Getting all settings")
    attrs = [key for key in dir(settings) if not key.startswith("_") and key.isupper()]
    all_settings = {}
    for attr in attrs:
        value = getattr(settings, attr)
        if type(value) is float or type(value) is int:
            all_settings[attr] = value
        elif type(value) is datetime.datetime:
            all_settings[attr] = value.isoformat()
        else:
            all_settings[attr] = str(value)
    additional_settings = await p_settings.load_settings()
    for key, value in additional_settings.items():
        all_settings[key] = value
    return web.json_response(all_settings, status=200)


def setup_routes(app) -> None:
    app.router.add_post("/api/download_log", post_download_log)
    app.router.add_get("/api/download_telemetry", get_download_telemetry)
    app.router.add_get("/api/download_events", get_download_events)
    app.router.add_post("/api/download_image", post_download_image)
    app.router.add_post("/api/set_melvin_task", post_set_melvin_task)
    app.router.add_get("/api/reset_settings", get_reset_settings)
    app.router.add_post("/api/set_setting", post_set_setting)
    app.router.add_post("/api/clear_setting", post_clear_setting)
    app.router.add_post("/api/clear_log", post_clear_log)
    app.router.add_post("/api/get_setting", post_get_setting)
    app.router.add_get("/api/get_all_settings", get_all_settings)
    app.router.add_post("/api/download_log_and_clear", post_download_log_and_clear)
    app.router.add_get(
        "/api/download_telemetry_and_clear", get_download_telemetry_and_clear
    )
    app.router.add_get("/api/download_events_and_clear", get_download_events_and_clear)
    app.router.add_post("/api/download_image_and_clear", post_download_image_and_clear)
    app.router.add_get("/api/clear_all_logs", get_clear_all_logs)
    app.router.add_get("/api/clear_telemetry", get_clear_telemetry)
    app.router.add_get("/api/clear_events", get_clear_events)
    app.router.add_get("/api/clear_images", get_clear_all_images)
    app.router.add_get("/api/health", health)
    app.router.add_get("/api/get_disk_usage", get_disk_usage)
    app.router.add_get("/api/get_memory_usage", get_memory_usage)
    app.router.add_get("/api/get_cpu_usage", get_cpu_usage)
    app.router.add_get("/api/restart_melvin", get_restart_melvin)
    app.router.add_get("/api/shutdown_melvin", get_shutdown_melvin)
    app.router.add_post("/api/execute_command", post_execute_command)
    app.router.add_get("/api/get_melvin_version", get_melvin_version)
    app.router.add_get("/api/list_log_files", get_list_log_files)
    app.router.add_get("/api/list_images", get_list_images)


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
