import asyncio

import pytest
from aiohttp import web, ClientSession
from aiohttp.test_utils import TestClient
from melvonaut import settings
from shared import constants as con
from melvonaut.api import setup_routes
from loguru import logger
from melvonaut.mel_telemetry import MelTelemetry
from shared.models import CameraAngle, State, Event
from datetime import datetime
from PIL import Image
from pathlib import Path
from io import BytesIO

mel_telemetry = MelTelemetry(
    active_time=0.0,
    angle=CameraAngle.Normal,
    area_covered=MelTelemetry.AreaCovered(narrow=0.0, normal=0.0, wide=0.0),
    battery=0.0,
    data_volume=MelTelemetry.DataVolume(data_volume_sent=0, data_volume_received=0),
    distance_covered=0.0,
    fuel=0.0,
    width_x=0,
    height_y=0,
    images_taken=0,
    max_battery=0.0,
    objectives_done=0,
    objectives_points=0,
    simulation_speed=0,
    state=State.Acquisition,
    timestamp=datetime.now(),
    vx=0.0,
    vy=0.0,
)

event = Event()

image_path = con.IMAGE_LOCATION.format(
    melv_id="test",
    angle="tele_angle",
    time=datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f"),
    cor_x=0,
    cor_y=0,
)

logs_test_lock = asyncio.Lock()


def generate_test_image():
    path = Path(con.IMAGE_PATH_BASE)
    if not path.exists():
        path.mkdir()
    im = Image.new("RGB", size=(100, 100), color=(155, 0, 0))
    im.save(image_path, "png")


@pytest.fixture(scope="session", autouse=True)
def enable_logging():
    settings.setup_logging()


@pytest.fixture
def caplog(caplog):
    handler_id = logger.add(caplog.handler, format="{message}")
    yield caplog
    logger.remove(handler_id)


@pytest.fixture
async def client(aiohttp_client: ClientSession) -> TestClient:
    app = web.Application()
    setup_routes(app)
    return await aiohttp_client(app)


async def test_health(client: TestClient):
    resp = await client.get("/api/health")
    assert resp.status == 200
    assert await resp.text() == "OK"


async def test_get_disk_usage(client: TestClient):
    resp = await client.get("/api/get_disk_usage")
    assert resp.status == 200
    data = await resp.json()
    assert "root" in data
    assert "home" in data


async def test_get_memory_usage(client: TestClient):
    resp = await client.get("/api/get_memory_usage")
    assert resp.status == 200
    data = await resp.json()
    assert "total" in data
    assert "available" in data


async def test_get_cpu_usage(client: TestClient):
    resp = await client.get("/api/get_cpu_usage")
    assert resp.status == 200
    data = await resp.json()
    assert "user" in data
    assert "system" in data
    assert "idle" in data
    assert "percent" in data
    assert "physical_cores" in data
    assert "current_freq" in data
    assert "max_freq" in data
    assert "min_freq" in data


async def test_get_restart_melvin(client: TestClient):
    resp = await client.get("/api/restart_melvin")
    assert resp.status == 501
    assert await resp.text() == "Not Implemented"


async def test_get_shutdown_melvin(client: TestClient, caplog):
    caplog.set_level("WARNING")
    settings.DO_ACTUALLY_EXIT = False
    resp = await client.get("/api/shutdown_melvin")
    assert resp.status == 200
    assert await resp.text() == "OK"
    assert "Requested shutdown, but not actually exiting" in caplog.text


async def test_post_execute_command(client: TestClient):
    resp = await client.post("/api/execute_command", json={"cmd": "echo hello"})
    assert resp.status == 200
    data = await resp.json()
    assert "output" in data
    assert "return_code" in data
    assert data["output"] == ["hello\n"]
    assert data["return_code"] == 0


async def test_get_melvin_version(client: TestClient):
    resp = await client.get("/api/get_melvin_version")
    assert resp.status == 200
    data = await resp.json()
    assert "version" in data


async def test_get_list_log_files(client: TestClient):
    async with logs_test_lock:
        logger.info("test_get_list_log_files")
        resp = await client.get("/api/list_log_files")
        assert resp.status == 200, await resp.text()
        data = await resp.json()
        assert "log_files" in data


async def test_post_download_log(client: TestClient):
    async with logs_test_lock:
        logger.info("test_post_download_log")
        resp = await client.get("/api/list_log_files")
        assert resp.status == 200
        log_file = (await resp.json())["log_files"][0]
        resp = await client.post("/api/download_log", json={"file": log_file})
        assert resp.status == 200
        data = await resp.text()
        assert "Listing log files" in data


async def test_post_download_log_and_clear(client: TestClient):
    async with logs_test_lock:
        logger.info("test_post_download_log_and_clear")
        resp = await client.get("/api/list_log_files")
        assert resp.status == 200
        log_file = (await resp.json())["log_files"][0]
        resp = await client.post("/api/download_log_and_clear", json={"file": log_file})
        assert resp.status == 200, await resp.text() + " " + log_file
        data = await resp.text()
        assert "Listing log files" in data


async def test_post_clear_log(client: TestClient):
    async with logs_test_lock:
        logger.info("test_post_clear_log")
        resp = await client.get("/api/list_log_files")
        assert resp.status == 200
        log_file = (await resp.json())["log_files"][0]
        resp = await client.post("/api/clear_log", json={"file": log_file})
        assert resp.status == 200, await resp.text()
        assert log_file in await resp.text()


async def test_get_clear_all_logs(client: TestClient):
    async with logs_test_lock:
        logger.info("test_get_clear_all_logs")
        resp = await client.get("/api/list_log_files")
        assert resp.status == 200
        data = await resp.json()
        log_file = data["log_files"][0]
        resp = await client.get("/api/clear_all_logs")
        assert resp.status == 200, await resp.text()
        data = await resp.json()
        assert "Cleared_files" in data
        assert log_file in data["Cleared_files"]


async def test_get_download_telemetry(client: TestClient):
    await mel_telemetry.store_observation_csv()
    resp = await client.get("/api/download_telemetry")
    assert resp.status == 200
    data = await resp.text()
    assert (
        "active_time,angle,area_covered_narrow,area_covered_normal,area_covered_wide,battery,"
        "data_volume_data_volume_received,data_volume_data_volume_sent,distance_covered,fuel,width_x,height_y,"
        "images_taken,max_battery,objectives_done,objectives_points,simulation_speed,state,timestamp,vx,vy"
    ) in data, data


async def test_get_download_telemetry_and_clear(client: TestClient):
    await mel_telemetry.store_observation_csv()
    resp = await client.get("/api/download_telemetry_and_clear")
    assert resp.status == 200
    data = await resp.text()
    assert (
        "active_time,angle,area_covered_narrow,area_covered_normal,area_covered_wide,battery,"
        "data_volume_data_volume_received,data_volume_data_volume_sent,distance_covered,fuel,width_x,height_y,"
        "images_taken,max_battery,objectives_done,objectives_points,simulation_speed,state,timestamp,vx,vy"
    ) in data, data
    resp = await client.get("/api/download_telemetry")
    assert resp.status == 404


async def test_get_clear_telemetry(client: TestClient):
    await mel_telemetry.store_observation_csv()
    resp = await client.get("/api/clear_telemetry")
    assert resp.status == 200
    assert await resp.text() == "OK"
    resp = await client.get("/api/download_telemetry")
    assert resp.status == 404


async def test_get_download_events(client: TestClient):
    await event.to_csv()
    resp = await client.get("/api/download_events")
    assert resp.status == 200
    data = await resp.text()
    assert "data,event,id,retry,timestamp,current_x,current_y" in data, data


async def test_get_download_events_and_clear(client: TestClient):
    await event.to_csv()
    resp = await client.get("/api/download_events_and_clear")
    assert resp.status == 200
    data = await resp.text()
    assert "data,event,id,retry,timestamp,current_x,current_y" in data, data
    resp = await client.get("/api/download_events")
    assert resp.status == 404


async def test_get_clear_events(client: TestClient):
    await event.to_csv()
    resp = await client.get("/api/clear_events")
    assert resp.status == 200
    assert await resp.text() == "OK"
    resp = await client.get("/api/download_events")
    assert resp.status == 404


async def test_get_list_images(client: TestClient):
    generate_test_image()
    resp = await client.get("/api/list_images")
    assert resp.status == 200, await resp.text()
    data = await resp.json()
    assert "images" in data
    assert Path(image_path).name in data["images"], data


async def test_post_download_image(client: TestClient):
    generate_test_image()
    resp = await client.get("/api/list_images")
    assert resp.status == 200
    image_file = (await resp.json())["images"][0]
    resp = await client.post("/api/download_image", json={"file": image_file})
    assert resp.status == 200, await resp.text()
    buffer = b""
    async for chunk in resp.content.iter_any():
        buffer += chunk
    im = Image.open(BytesIO(buffer))
    assert im.mode == "RGB"
    assert im.size == (100, 100)


async def test_post_download_image_and_clear(client: TestClient):
    generate_test_image()
    resp = await client.get("/api/list_images")
    assert resp.status == 200
    image_file = (await resp.json())["images"][0]
    resp = await client.post("/api/download_image_and_clear", json={"file": image_file})
    assert resp.status == 200
    buffer = b""
    async for chunk in resp.content.iter_any():
        buffer += chunk
    im = Image.open(BytesIO(buffer))
    assert im.mode == "RGB"
    assert im.size == (100, 100)
    resp = await client.get("/api/list_images")
    assert resp.status == 200
    data = await resp.json()
    assert image_file not in data["images"]


async def test_get_clear_all_images(client: TestClient):
    generate_test_image()
    resp = await client.get("/api/list_images")
    assert resp.status == 200
    image_file = (await resp.json())["images"][0]
    resp = await client.get("/api/clear_images")
    assert resp.status == 200
    resp = await client.get("/api/list_images")
    assert resp.status == 200
    data = await resp.json()
    assert image_file not in data["images"]


async def test_post_set_melvin_task(client: TestClient):
    resp = await client.post("/api/get_setting", json={"CURRENT_MELVIN_TASK": ""})
    assert resp.status == 200
    data = await resp.json()
    assert "CURRENT_MELVIN_TASK" in data
    previous_task = data["CURRENT_MELVIN_TASK"]
    if previous_task != "mapping":
        new_task = "mapping"
    else:
        new_task = "ebt"
    resp = await client.post("/api/set_melvin_task", json={"task": new_task})
    assert resp.status == 200, await resp.text()
    resp = await client.post("/api/get_setting", json={"CURRENT_MELVIN_TASK": ""})
    assert resp.status == 200
    data = await resp.json()
    assert "CURRENT_MELVIN_TASK" in data
    assert data["CURRENT_MELVIN_TASK"] == new_task


async def test_get_reset_settings(client: TestClient):
    resp = await client.post(
        "/api/set_setting",
        json={"TARGET_CAMERA_ANGLE_ACQUISITION": "wide", "DISTANCE_BETWEEN_IMAGES": 0},
    )
    assert resp.status == 200
    resp = await client.post(
        "/api/get_setting",
        json={"TARGET_CAMERA_ANGLE_ACQUISITION": "", "DISTANCE_BETWEEN_IMAGES": ""},
    )
    assert resp.status == 200
    data = await resp.json()
    assert "TARGET_CAMERA_ANGLE_ACQUISITION" in data
    assert "DISTANCE_BETWEEN_IMAGES" in data
    assert data["TARGET_CAMERA_ANGLE_ACQUISITION"] == "wide"
    assert data["DISTANCE_BETWEEN_IMAGES"] == 0
    resp = await client.get("/api/reset_settings")
    assert resp.status == 200
    resp = await client.post(
        "/api/get_setting",
        json={"TARGET_CAMERA_ANGLE_ACQUISITION": "", "DISTANCE_BETWEEN_IMAGES": ""},
    )
    assert resp.status == 200
    data = await resp.json()
    assert "TARGET_CAMERA_ANGLE_ACQUISITION" in data
    assert "DISTANCE_BETWEEN_IMAGES" in data
    assert data["TARGET_CAMERA_ANGLE_ACQUISITION"] == "normal"
    assert data["DISTANCE_BETWEEN_IMAGES"] == 350


async def test_post_set_setting(client: TestClient):
    resp = await client.post(
        "/api/set_setting",
        json={"TARGET_CAMERA_ANGLE_ACQUISITION": "wide", "DISTANCE_BETWEEN_IMAGES": 0},
    )
    assert resp.status == 200
    resp = await client.post(
        "/api/get_setting",
        json={"TARGET_CAMERA_ANGLE_ACQUISITION": "", "DISTANCE_BETWEEN_IMAGES": ""},
    )
    assert resp.status == 200
    data = await resp.json()
    assert "TARGET_CAMERA_ANGLE_ACQUISITION" in data
    assert "DISTANCE_BETWEEN_IMAGES" in data
    assert data["TARGET_CAMERA_ANGLE_ACQUISITION"] == "wide"
    assert data["DISTANCE_BETWEEN_IMAGES"] == 0


async def test_post_clear_setting(client: TestClient):
    resp = await client.post(
        "/api/set_setting",
        json={"TARGET_CAMERA_ANGLE_ACQUISITION": "wide", "DISTANCE_BETWEEN_IMAGES": 0},
    )
    assert resp.status == 200
    resp = await client.post(
        "/api/get_setting",
        json={"TARGET_CAMERA_ANGLE_ACQUISITION": "", "DISTANCE_BETWEEN_IMAGES": ""},
    )
    assert resp.status == 200
    data = await resp.json()
    assert "TARGET_CAMERA_ANGLE_ACQUISITION" in data
    assert "DISTANCE_BETWEEN_IMAGES" in data
    assert data["TARGET_CAMERA_ANGLE_ACQUISITION"] == "wide"
    assert data["DISTANCE_BETWEEN_IMAGES"] == 0
    resp = await client.post(
        "/api/clear_setting",
        json={"TARGET_CAMERA_ANGLE_ACQUISITION": "", "DISTANCE_BETWEEN_IMAGES": ""},
    )
    assert resp.status == 200
    resp = await client.post(
        "/api/get_setting",
        json={"TARGET_CAMERA_ANGLE_ACQUISITION": "", "DISTANCE_BETWEEN_IMAGES": ""},
    )
    assert resp.status == 200
    data = await resp.json()
    assert "TARGET_CAMERA_ANGLE_ACQUISITION" in data
    assert "DISTANCE_BETWEEN_IMAGES" in data
    assert data["TARGET_CAMERA_ANGLE_ACQUISITION"] == "normal"
    assert data["DISTANCE_BETWEEN_IMAGES"] == 350


async def test_get_setting(client: TestClient):
    resp = await client.post(
        "/api/get_setting",
        json={"TARGET_CAMERA_ANGLE_ACQUISITION": "", "DISTANCE_BETWEEN_IMAGES": ""},
    )
    assert resp.status == 200
    data = await resp.json()
    assert "TARGET_CAMERA_ANGLE_ACQUISITION" in data
    assert "DISTANCE_BETWEEN_IMAGES" in data
    assert data["TARGET_CAMERA_ANGLE_ACQUISITION"] == "normal"
    assert data["DISTANCE_BETWEEN_IMAGES"] == 350


async def test_get_all_settings(client: TestClient):
    resp = await client.get("/api/get_all_settings")
    assert resp.status == 200, await resp.text()
    data = await resp.json()
    assert "TARGET_CAMERA_ANGLE_ACQUISITION" in data
    assert "DISTANCE_BETWEEN_IMAGES" in data
    assert data["TARGET_CAMERA_ANGLE_ACQUISITION"] == "normal", data[
        "TARGET_CAMERA_ANGLE_ACQUISITION"
    ]
    assert data["DISTANCE_BETWEEN_IMAGES"] == 350, data["DISTANCE_BETWEEN_IMAGES"]
