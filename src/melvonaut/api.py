from melvonaut.settings import settings
import importlib.metadata
import psutil
from aiohttp import web, hdrs
from io import StringIO, BytesIO
from aiohttp.web_response import ContentCoding
from typing import Callable, Any, Awaitable
from melvonaut import utils
from shared import constants as con
from loguru import logger
import asyncio
import pathlib
import shared.models as models
import datetime


Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


async def health(request: web.Request) -> web.Response:
    """Check if the API is running and healthy.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.Response: A response with status 200 and text "OK".
    """
    return web.Response(status=200, text="OK")


async def get_disk_usage(request: web.Request) -> web.Response:
    """Retrieve disk usage statistics for root and home directories.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.Response: JSON response containing disk usage data.
    """
    logger.debug("Getting disk usage")
    disk_root = psutil.disk_usage("/")
    disk_home = psutil.disk_usage("/home")
    return web.json_response(
        {"root": disk_root._asdict(), "home": disk_home._asdict()}, status=200
    )


async def get_memory_usage(request: web.Request) -> web.Response:
    """Retrieve memory usage statistics.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.Response: JSON response containing memory usage data.
    """
    logger.debug("Getting memory usage")
    memory_usage = psutil.virtual_memory()
    return web.json_response(memory_usage._asdict(), status=200)


async def get_cpu_usage(request: web.Request) -> web.Response:
    """Retrieve CPU usage statistics.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.Response: JSON response containing CPU usage data including user, system, idle time, percent usage, core count, and frequency.
    """
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


async def get_restart_melvin(request: web.Request) -> web.Response:
    """Handles a request to restart the Melvin service.

    This endpoint is not yet implemented and always returns a 501 Not Implemented response.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.Response: A response indicating that the operation is not implemented.
    """
    return web.Response(status=501, text="Not Implemented")


async def get_shutdown_melvin(request: web.Request) -> web.Response:
    """Handles a request to shut down the Melvin service.

    If `settings.DO_ACTUALLY_EXIT` is set to True, the event loop is stopped,
    all pending tasks are canceled, and the process exits. Otherwise, a warning is logged.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.Response: A response with status 200 indicating the shutdown request was received.
    """
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


async def post_execute_command(request: web.Request) -> web.Response:
    """Execute a shell command asynchronously.

    Args:
        request (web.Request): The incoming HTTP request containing JSON data with the command to execute.

    Returns:
        web.Response: JSON response containing command output and return code.
    """
    data = await request.json()
    cmd = data.get("cmd")
    logger.debug(f"Executing command: {cmd}")
    output = []
    try:
        process = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        while True:
            if process.stdout:
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


async def get_melvin_version(request: web.Request) -> web.Response:
    """Retrieve the current version of the Melvin service.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.Response: JSON response containing the Melvin service version.
    """
    return web.json_response(
        {"version": importlib.metadata.version("ciarc")}, status=200
    )


async def get_list_log_files(request: web.Request) -> web.Response:
    """Retrieve a list of log files from the log directory.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.Response: JSON response containing a list of log filenames.
    """
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


async def post_download_log(request: web.Request) -> web.Response | web.FileResponse:
    """Handles log file download requests.

    Args:
        request (web.Request): The incoming HTTP request containing the log file name in JSON format.

    Returns:
        web.Response: The requested log file if it exists, otherwise a 404 response.
    """
    data = await request.json()
    logger.debug(f"Downloading log: {data}")
    log_file = pathlib.Path(con.MEL_LOG_PATH) / data.get("file")
    if log_file.exists():
        return web.FileResponse(log_file, status=200)
    else:
        return web.Response(status=404, text="File not found")


async def post_download_log_and_clear(request: web.Request) -> web.Response:
    """Handles log file download requests and deletes the file after serving it.

    Args:
        request (web.Request): The incoming HTTP request containing the log file name in JSON format.

    Returns:
        web.Response: The requested log file if it exists, otherwise a 404 response.
    """
    data = await request.json()
    logger.debug(f"Downloading log and clearing: {data}")
    log_file = pathlib.Path(con.MEL_LOG_PATH) / data.get("file")
    if log_file.exists():
        log_file_content = StringIO(log_file.read_text())
        try:
            return web.Response(body=log_file_content, status=200)
        finally:
            log_file.unlink()
            utils.setup_file_logging()
    else:
        return web.Response(status=404, text="File not found")


async def post_clear_log(request: web.Request) -> web.Response:
    """Handles log file deletion requests.

    Args:
        request (web.Request): The incoming HTTP request containing the log file name in JSON format.

    Returns:
        web.Response: A success response if the log file is cleared, otherwise an error response.
    """
    data = await request.json()
    logger.debug(f"Clearing log: {data}")
    log_file = pathlib.Path(con.MEL_LOG_PATH) / data.get("file")
    if log_file.exists():
        if log_file.is_dir():
            return web.Response(status=400, text=f"{log_file} is a directory")
        if not log_file.name.endswith(".log"):
            return web.Response(status=400, text=f"{log_file} is not a log file")
        log_file.unlink()
        utils.setup_file_logging()
        return web.Response(status=200, text=f"{log_file} cleared")
    else:
        return web.Response(status=404, text=f"{log_file} not found")


async def get_clear_all_logs(request: web.Request) -> web.Response:
    """Clears all log files in the system.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.Response: JSON response containing a list of cleared log files.
    """
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
        utils.setup_file_logging()
        return web.json_response({"Cleared_files": log_files}, status=200)
    except Exception as e:
        logger.exception(e)
        return web.json_response({"error": str(e)}, status=500)


# Download telemetry
async def get_download_telemetry(
    request: web.Request,
) -> web.Response | web.FileResponse:
    """Handles telemetry data download requests.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.Response: The telemetry file if it exists, otherwise a 404 response.
    """
    logger.debug("Downloading telemetry")
    telemetry_file = pathlib.Path(con.TELEMETRY_LOCATION_CSV)
    if telemetry_file.exists():
        return web.FileResponse(telemetry_file, status=200)
    else:
        return web.Response(status=404, text="File not found")


async def get_download_telemetry_and_clear(request: web.Request) -> web.Response:
    """Handles telemetry data download requests and deletes the file after serving it.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.Response: The telemetry file if it exists, otherwise a 404 response.
    """
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


async def get_clear_telemetry(request: web.Request) -> web.Response:
    """Clears the telemetry data file.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.Response: A success response if the file is deleted, otherwise a 404 response.
    """
    logger.debug("Clearing telemetry")
    telemetry_file = pathlib.Path(con.TELEMETRY_LOCATION_CSV)
    if telemetry_file.exists():
        telemetry_file.unlink()
        return web.Response(status=200, text="OK")
    else:
        return web.Response(status=404, text="File not found")


# Download events
async def get_download_events(request: web.Request) -> web.Response | web.FileResponse:
    """Handles the download of event logs.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.FileResponse: The requested event log file if it exists.
        web.Response: A 404 response if the file is not found.
    """
    logger.debug("Downloading events")
    events_file = pathlib.Path(con.EVENT_LOCATION_CSV)
    if events_file.exists():
        return web.FileResponse(events_file, status=200)
    else:
        return web.Response(status=404, text="File not found")


async def get_download_events_and_clear(request: web.Request) -> web.Response:
    """Downloads and clears the event log file.

    This function retrieves the event log file, sends its content as a response,
    and then deletes the file from the system.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.Response: A response containing the event log content if found.
        web.Response: A 404 response if the file is not found.
    """
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


async def get_clear_events(request: web.Request) -> web.Response:
    """Deletes the event log file from the system.

    If the event log file exists, it is deleted. If it does not exist, a 404 response is returned.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.Response: A 200 response if the file is successfully deleted.
        web.Response: A 404 response if the file is not found.
    """
    logger.debug("Clearing events")
    events_file = pathlib.Path(con.EVENT_LOCATION_CSV)
    if events_file.exists():
        events_file.unlink()
        return web.Response(status=200, text="OK")
    else:
        return web.Response(status=404, text="File not found")


async def get_list_images(request: web.Request) -> web.Response:
    """Lists all available image files.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.Response: JSON response containing a list of image filenames.
    """
    logger.debug("Listing images")
    folder = pathlib.Path(con.IMAGE_PATH_BASE)
    if not folder.exists():
        return web.Response(status=404, text=f"Folder not found: {folder}")
    images = [str(file.name) for file in folder.rglob("*.png") if file.is_file()]
    return web.json_response({"images": images}, status=200)


async def post_download_image(request: web.Request) -> web.Response | web.FileResponse:
    """Handles image file download requests.

    Args:
        request (web.Request): The incoming HTTP request containing the image filename in JSON format.

    Returns:
        web.Response: The requested image file if it exists, otherwise a 404 response.
    """
    data = await request.json()
    logger.debug(f"Downloading image: {data}")
    image_file = pathlib.Path(con.IMAGE_PATH_BASE) / data.get("file")
    if image_file.exists():
        return web.FileResponse(image_file, status=200)
    else:
        return web.Response(status=404, text="File not found")


async def post_download_image_and_clear(request: web.Request) -> web.Response:
    """Handles image file download requests and deletes the file after serving it.

    Args:
        request (web.Request): The incoming HTTP request containing the image filename in JSON format.

    Returns:
        web.Response: The requested image file if it exists, otherwise a 404 response.
    """
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


async def get_clear_all_images(request: web.Request) -> web.Response:
    """Clears all stored images.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.Response: JSON response containing a list of cleared images.
    """
    logger.debug("Clearing all images")
    folder = pathlib.Path(con.IMAGE_PATH_BASE)
    images = [str(file) for file in folder.rglob("*.png") if file.is_file()]
    for image in images:
        pathlib.Path(image).unlink()
    return web.Response(status=200, text="OK")


async def post_set_melvin_task(request: web.Request) -> web.Response:
    """Sets a task for Melvin (a task management system).

    Args:
        request (web.Request): The incoming HTTP request containing the task details in JSON format.

    Returns:
        web.Response: A success response if the task is set.
    """
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
    settings.set_settings({"CURRENT_MELVIN_TASK": melvin_task})
    return web.Response(status=200, text="OK")


async def get_reset_settings(request: web.Request) -> web.Response:
    """Resets all settings to their default values.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.Response: A success response confirming the reset.
    """
    logger.debug("Resetting settings")
    settings.clear_settings()
    return web.Response(status=200, text="OK")


async def post_set_setting(request: web.Request) -> web.Response:
    """Sets a new configuration setting.

    Args:
        request (web.Request): The incoming HTTP request containing settings in JSON format.

    Returns:
        web.Response: A success response if the setting is applied.
    """
    logger.debug("Setting settings")
    data = await request.json()
    logger.debug(f"Setting settings: {data}")
    settings.set_settings(data)
    return web.Response(status=200, text="OK")


async def post_clear_setting(request: web.Request) -> web.Response:
    """Clears a specific setting.

    Args:
        request (web.Request): The incoming HTTP request containing the setting name in JSON format.

    Returns:
        web.Response: A success response if the setting is cleared.
    """
    logger.debug("Clearing settings")
    data = await request.json()
    logger.debug(f"Clearing settings: {data}")
    settings.delete_settings(data.keys())
    return web.Response(status=200, text="OK")


async def post_get_setting(request: web.Request) -> web.Response:
    """Retrieves a specific setting.

    Args:
        request (web.Request): The incoming HTTP request containing the setting name in JSON format.

    Returns:
        web.Response: JSON response containing the requested setting value.
    """
    logger.debug("Getting settings")
    data = await request.json()
    logger.debug(f"Requested settings: {data}")
    response_settings = {}
    try:
        for key in data.keys():
            response_settings[key] = settings.__getattribute__(key)
    except AttributeError:
        return web.Response(status=404, text=f"Setting not found: {key}")
    logger.debug(f"Response settings: {response_settings}")
    return web.json_response(response_settings, status=200)


async def get_all_settings(request: web.Request) -> web.Response:
    """Retrieve all settings configured in the system.

    Args:
        request (web.Request): The incoming HTTP request.

    Returns:
        web.Response: JSON response containing all system settings.
    """
    logger.debug("Getting all settings")
    attrs = [key for key in dir(settings) if not key.startswith("_") and key.isupper()]
    all_settings: dict[str, Any] = {}
    for attr in attrs:
        value = settings.__getattribute__(attr)
        if type(value) is float or type(value) is int:
            all_settings[attr] = value
        elif type(value) is datetime.datetime:
            all_settings[attr] = value.isoformat()
        else:
            all_settings[attr] = str(value)
    return web.json_response(all_settings, status=200)


def setup_routes(app: web.Application) -> None:
    """Sets up API routes for the web application.

    Args:
        app (web.Application): The web application instance.
    """
    app.router.add_post("/api/post_download_log", post_download_log)
    app.router.add_get("/api/get_download_telemetry", get_download_telemetry)
    app.router.add_get("/api/get_download_events", get_download_events)
    app.router.add_post("/api/post_download_image", post_download_image)
    app.router.add_post("/api/post_set_melvin_task", post_set_melvin_task)
    app.router.add_get("/api/get_reset_settings", get_reset_settings)
    app.router.add_post("/api/post_set_setting", post_set_setting)
    app.router.add_post("/api/post_clear_setting", post_clear_setting)
    app.router.add_post("/api/post_clear_log", post_clear_log)
    app.router.add_post("/api/post_get_setting", post_get_setting)
    app.router.add_get("/api/get_all_settings", get_all_settings)
    app.router.add_post("/api/post_download_log_and_clear", post_download_log_and_clear)
    app.router.add_get(
        "/api/get_download_telemetry_and_clear", get_download_telemetry_and_clear
    )
    app.router.add_get(
        "/api/get_download_events_and_clear", get_download_events_and_clear
    )
    app.router.add_post(
        "/api/post_download_image_and_clear", post_download_image_and_clear
    )
    app.router.add_get("/api/get_clear_all_logs", get_clear_all_logs)
    app.router.add_get("/api/get_clear_telemetry", get_clear_telemetry)
    app.router.add_get("/api/get_clear_events", get_clear_events)
    app.router.add_get("/api/get_clear_all_images", get_clear_all_images)
    app.router.add_get("/api/health", health)
    app.router.add_get("/api/get_disk_usage", get_disk_usage)
    app.router.add_get("/api/get_memory_usage", get_memory_usage)
    app.router.add_get("/api/get_cpu_usage", get_cpu_usage)
    app.router.add_get("/api/get_restart_melvin", get_restart_melvin)
    app.router.add_get("/api/get_shutdown_melvin", get_shutdown_melvin)
    app.router.add_post("/api/post_execute_command", post_execute_command)
    app.router.add_get("/api/get_melvin_version", get_melvin_version)
    app.router.add_get("/api/get_list_log_files", get_list_log_files)
    app.router.add_get("/api/get_list_images", get_list_images)


@web.middleware
async def compression_middleware(request: web.Request, handler: Handler) -> Any:
    accept_encoding = request.headers.get(hdrs.ACCEPT_ENCODING, "").lower()

    if ContentCoding.gzip.value in accept_encoding:
        compressor = ContentCoding.gzip.value
    elif ContentCoding.deflate.value in accept_encoding:
        compressor = ContentCoding.deflate.value
    else:
        return await handler(request)

    resp = await handler(request)
    resp.headers[hdrs.CONTENT_ENCODING] = compressor
    resp.enable_compression()
    return resp


@web.middleware
async def catcher_middleware(request: web.Request, handler: Handler) -> Any:
    try:
        return await handler(request)
    except Exception as e:
        logger.exception(e)
        return web.Response(status=500, text=str(e))


async def run_api() -> None:
    """Starts the web API server.

    Returns:
        None
    """
    logger.debug("Setting up API server")
    settings.init_settings()
    app = web.Application(middlewares=[compression_middleware, catcher_middleware])
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
