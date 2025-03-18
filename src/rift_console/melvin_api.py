from typing import Any, Optional
from pydantic import BaseModel
import requests

from loguru import logger
from shared.models import HttpCode

# TODO
url = "0.0.0.0"
port = "8080"


def melvonaut_api(
    method: HttpCode,
    endpoint: str,
) -> Any:
    try:
        with requests.Session() as s:
            match method:
                case HttpCode.GET:
                    r = s.get("http://" + url + ":" + port + endpoint, timeout=5)

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
        case _:
            # unknow error
            logger.warning(f"Unkown error, could not contact satellite? - {r}.")
            return {}


class MelvonautTelemetry(BaseModel):
    disk_total: int
    disk_free: int
    disk_perc: float
    mem_total: int
    mem_available: int
    mem_perc: float
    cpu_cores: int
    cpu_perc: float


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
    return None
