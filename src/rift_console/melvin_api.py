from typing import Any, Optional
import paramiko
from pydantic import BaseModel
import requests
import csv

from loguru import logger
from shared.models import HttpCode, live_utc
import shared.constants as con

# TODO
url = "localhost"
port = "8080"

# ssh melvin -N -L 8080:localhost:8080 -o ConnectTimeout=1s


def melvonaut_api(method: HttpCode, endpoint: str, json: dict[str, str] = {}) -> Any:
    try:
        with requests.Session() as s:
            match method:
                case HttpCode.GET:
                    r = s.get("http://" + url + ":" + port + endpoint, timeout=5)
                case HttpCode.POST:
                    r = s.post(
                        "http://" + url + ":" + port + endpoint,
                        timeout=5,
                        json=json,
                    )

    except requests.exceptions.ConnectionError:
        logger.error("ConnectionError - possible no VPN?")
        return {}
    except requests.exceptions.ReadTimeout:
        logger.error("Timeout error!")
        return {}

    match r.status_code:
        case 200:
            try:
                logger.debug(
                    f"Received from API {method}/{endpoint} - {r} - {r.json()}"
                )
            except requests.exceptions.JSONDecodeError:
                logger.debug(f"Received from API {method}/{endpoint} - {r}")
            return r
        case 404:
            logger.warning(f"Requested ressource not found - {r}.")
            return {}
        case _:
            # unknow error
            logger.warning(f"Unknown error, could not contact satellite? - {r}.")
            return {}


# # TODO not tested so far
# def melvonaut_api(method: HttpCode, endpoint: str, json: dict[str, str] = {}) -> Any:
#     with open(".ssh-pw") as file:
#         PASSWORD = file.read()
#     REMOTE_USER = "root"  # Remote SSH username
#     REMOTE_HOST = "10.100.50.1"  # Remote host IP
#     LOCAL_PORT = 8080  # Local port to forward
#     REMOTE_PORT = 8080  # Remote port to forward to

#     # Create an SSH client
#     client = paramiko.SSHClient()
#     client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

#     try:
#         # Connect to the remote host using the given password
#         client.connect(hostname=REMOTE_HOST, username=REMOTE_USER, password=PASSWORD)

#         # Set up port forwarding
#         transport = client.get_transport()
#         local_address = ("localhost", LOCAL_PORT)
#         remote_address = ("localhost", REMOTE_PORT)
#         if transport:
#             channel = transport.open_channel(
#                 "direct-tcpip", remote_address, local_address
#             )

#         logger.info(f"Port forwarding {LOCAL_PORT} -> {REMOTE_PORT} on {REMOTE_HOST}")
#         return melvonaut_api(method=method, endpoint=endpoint, json=json)

#     except Exception as e:
#         logger.error(f"An error occurred: {e}")

#     finally:
#         logger.info(f"Close tunnel.")
#         channel.close()
#         client.close()


class MelvonautTelemetry(BaseModel):
    disk_total: int
    disk_free: int
    disk_perc: float
    mem_total: int
    mem_available: int
    mem_perc: float
    cpu_cores: int
    cpu_perc: float


def clear_events() -> str:
    if not melvonaut_api(method=HttpCode.GET, endpoint="/api/health"):
        logger.warning("Melvonaut API unreachable!")
        return ""

    r = melvonaut_api(method=HttpCode.GET, endpoint="/api/get_clear_events")

    if r:
        res = "Mevlonaut get_clear_events done."
    else:
        res = "Mevlonaut get_clear_events failed, is okay if event-log is empty."
    logger.warning(res)
    return res


def get_setting(setting: str) -> str:
    if not melvonaut_api(method=HttpCode.GET, endpoint="/api/health"):
        logger.warning("Melvonaut API unreachable!")
        return ""
    check = melvonaut_api(
        method=HttpCode.POST, endpoint="/api/post_get_setting", json={setting: ""}
    )

    if check:
        value = str(check.json()[setting])
        logger.info(f'Mevlonaut get settting "{setting}" is "{value}" done.')
        return value
    logger.warning('Mevlonaut get setting "{setting}" failed.')
    return ""


def set_setting(setting: str, value: str) -> bool:
    if not melvonaut_api(method=HttpCode.GET, endpoint="/api/health"):
        logger.warning("Melvonaut API unreachable!")
        return False
    r = melvonaut_api(
        method=HttpCode.POST, endpoint="/api/post_set_setting", json={setting: value}
    )

    if r:
        check = melvonaut_api(
            method=HttpCode.POST, endpoint="/api/post_get_setting", json={setting: ""}
        )
        logger.error(f"{check.json()} {value}")
        if check.json()[setting] == value:
            logger.info(f'Mevlonaut set_Settting "{setting}" to "{value}" done.')
            return True
    logger.warning(f'Mevlonaut set_Settting "{setting}" to "{value}" failed.')
    return False


def download_events() -> str:
    if not melvonaut_api(method=HttpCode.GET, endpoint="/api/health"):
        logger.warning("Melvonaut API unreachable!")
        return ""

    r = melvonaut_api(method=HttpCode.GET, endpoint="/api/get_download_events")
    if r:
        decoded_content = r.content.decode("utf-8")
        csv_file_path = (
            con.CONSOLE_FROM_MELVONAUT_PATH
            + "MelvonautEvents-"
            + live_utc().strftime("%Y-%m-%dT%H:%M:%S")
            + ".csv"
        )

        with open(csv_file_path, "w", newline="", encoding="utf-8") as file:
            file.write(decoded_content)
        with open(csv_file_path, mode="r", newline="", encoding="utf-8") as file:
            csv_reader = csv.reader(file)
            line_count = sum(1 for _ in csv_reader)

        res = f"Mevlonaut get_download_events to {csv_file_path} with {line_count} lines done."
    else:
        res = "Mevlonaut get_download_events failed, is okay if event-log is empty."
    logger.warning(res)
    return res


def clear_telemetry() -> str:
    if not melvonaut_api(method=HttpCode.GET, endpoint="/api/health"):
        logger.warning("Melvonaut API unreachable!")
        return ""

    r = melvonaut_api(method=HttpCode.GET, endpoint="/api/get_clear_telemetry")

    if r:
        res = "Mevlonaut clear_telemetry done."
    else:
        res = "Mevlonaut clear_telemetry failed."

    logger.warning(res)
    return res


def download_telemetry() -> str:
    if not melvonaut_api(method=HttpCode.GET, endpoint="/api/health"):
        logger.warning("Melvonaut API unreachable!")
        return ""

    r = melvonaut_api(method=HttpCode.GET, endpoint="/api/get_download_telemetry")
    if r:
        decoded_content = r.content.decode("utf-8")
        csv_file_path = (
            con.CONSOLE_FROM_MELVONAUT_PATH
            + "MelvonautTelemetry-"
            + live_utc().strftime("%Y-%m-%dT%H:%M:%S")
            + ".csv"
        )

        with open(csv_file_path, "w", newline="", encoding="utf-8") as file:
            file.write(decoded_content)
        with open(csv_file_path, mode="r", newline="", encoding="utf-8") as file:
            csv_reader = csv.reader(file)
            line_count = sum(1 for _ in csv_reader)

        res = f"Mevlonaut download_telemetry to {csv_file_path} with {line_count} lines done."
    else:
        res = "Mevlonaut download_telemetry failed."
    logger.warning(res)
    return res


def clear_images() -> bool:
    if not melvonaut_api(method=HttpCode.GET, endpoint="/api/health"):
        logger.warning("Melvonaut API unreachable!")
        return False

    r = melvonaut_api(method=HttpCode.GET, endpoint="/api/get_clear_all_images")

    if r:
        logger.warning("Mevlonaut cleared all images done.")
        return True
    else:
        logger.warning("Mevlonaut clear_images failed.")
        return False


def clear_logs() -> bool:
    if not melvonaut_api(method=HttpCode.GET, endpoint="/api/health"):
        logger.warning("Melvonaut API unreachable!")
        return False

    r = melvonaut_api(method=HttpCode.GET, endpoint="/api/get_clear_all_logs")

    if r:
        logger.warning("Mevlonaut cleared all logs done.")
        return True
    else:
        logger.warning("Mevlonaut clear_logs failed.")
        return False


def get_download_save_log(log_name: str) -> Any:
    if not melvonaut_api(method=HttpCode.GET, endpoint="/api/health"):
        logger.warning("Melvonaut API unreachable!")
        return None

    r = melvonaut_api(
        method=HttpCode.POST, endpoint="/api/post_download_log", json={"file": log_name}
    )

    if r:
        logger.info(f'Mevlonaut downloaded "{log_name}" done.')
        return r
    else:
        logger.warning("Mevlonaut get_download_save_log failed.")
        return None


def list_logs() -> list[str] | bool:
    if not melvonaut_api(method=HttpCode.GET, endpoint="/api/health"):
        logger.warning("Melvonaut API unreachable!")
        return False

    r = melvonaut_api(method=HttpCode.GET, endpoint="/api/get_list_log_files").json()

    if r:
        logs: list[str] = r["log_files"]
        logger.info(f"Mevlonaut list logs done, found {len(logs)} images.")
        return logs
    else:
        logger.warning("Mevlonaut list_images failed.")
        return False


def get_download_save_image(image_name: str) -> Any:
    if not melvonaut_api(method=HttpCode.GET, endpoint="/api/health"):
        logger.warning("Melvonaut API unreachable!")
        return None

    r = melvonaut_api(
        method=HttpCode.POST,
        endpoint="/api/post_download_image",
        json={"file": image_name},
    )

    if r:
        logger.info(f'Mevlonaut downloaded "{image_name}" done.')
        return r
    else:
        logger.warning("Mevlonaut get_download_save_image failed.")
        return None


def list_images() -> list[str] | bool:
    if not melvonaut_api(method=HttpCode.GET, endpoint="/api/health"):
        logger.warning("Melvonaut API unreachable!")
        return False

    r = melvonaut_api(method=HttpCode.GET, endpoint="/api/get_list_images").json()

    if r:
        images: list[str] = r["images"]
        logger.info(f"Mevlonaut image list done, found {len(images)} images.")
        return images
    else:
        logger.warning("Mevlonaut list_images failed.")
        return False


def live_melvonaut() -> Optional[MelvonautTelemetry]:
    if not melvonaut_api(method=HttpCode.GET, endpoint="/api/health"):
        logger.warning("Melvonaut API unreachable!")
        return None
    d = melvonaut_api(method=HttpCode.GET, endpoint="/api/get_disk_usage").json()
    m = melvonaut_api(method=HttpCode.GET, endpoint="/api/get_memory_usage").json()
    c = melvonaut_api(method=HttpCode.GET, endpoint="/api/get_cpu_usage").json()

    gigabyte = 2**30
    if d and m and c:
        logger.info("Mevlonaut telemetry done.")
        return MelvonautTelemetry(
            disk_total=int(d["root"]["total"] / gigabyte),
            disk_free=int(d["root"]["free"] / gigabyte),
            disk_perc=100 - d["root"]["percent"],  # invert
            mem_total=int(m["total"] / gigabyte),
            mem_available=int(m["available"] / gigabyte),
            mem_perc=m["percent"],
            cpu_cores=c["physical_cores"],
            cpu_perc=c["percent"],
        )
    else:
        logger.warning("Mevlonaut telemetry failed.")
        return None
