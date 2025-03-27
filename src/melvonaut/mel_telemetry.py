##### TELEMETRY #####
import asyncio
import datetime
import json
from typing import Any

from aiofile import async_open
from pathlib import Path
import csv

import shared.constants as con
from shared.models import BaseTelemetry
from loguru import logger


class MelTelemetry(BaseTelemetry):
    timestamp: datetime.datetime

    async def store_observation_csv(self) -> None:
        """
        Stores the telemetry observation data in a CSV file.

        This function converts the telemetry data into a flattened dictionary format,
        ensuring nested dictionaries are stored as separate fields. It then appends
        the data to an existing CSV file or creates a new file if one does not exist.

        Args:
            None

        Returns:
            None
        """
        tel_dict = self.model_dump()
        flattened = {}
        for key, value in tel_dict.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    flattened[f"{key}_{sub_key}"] = sub_value
            else:
                flattened[key] = value
        if self.timestamp:
            timestamp = self.timestamp.isoformat()
        else:
            timestamp = datetime.datetime.now().isoformat()
        flattened["timestamp"] = timestamp

        if not Path(con.TELEMETRY_LOCATION_CSV).is_file():
            async with async_open(con.TELEMETRY_LOCATION_CSV, "w") as afp:
                writer = csv.DictWriter(afp, fieldnames=flattened.keys())
                await writer.writeheader()
                await writer.writerow(flattened)
            # logger.debug(f"Writing observation to {con.TELEMETRY_LOCATION_CSV}")
        else:
            async with async_open(con.TELEMETRY_LOCATION_CSV, "a") as afp:
                writer = csv.DictWriter(afp, fieldnames=flattened.keys())
                await writer.writerow(flattened)
            # logger.debug(f"Writing observation to {con.TELEMETRY_LOCATION_CSV}")

    async def store_observation_json(self) -> None:
        """
        Stores the telemetry observation data in a JSON file.

        This function retrieves the existing telemetry data from the JSON file
        and updates it with a new entry. If the JSON file does not exist, a new
        one is created. The data is formatted in a structured manner with timestamps
        as keys.

        Args:
            None

        Returns:
            None
        """
        logger.debug("Storing observation as json.")
        try:
            async with async_open(con.TELEMETRY_LOCATION_JSON, "r") as afp:
                raw_telemetry = await afp.read()
                dict_telemetry = json.loads(raw_telemetry)
        except FileNotFoundError:
            logger.debug(f"{con.TELEMETRY_LOCATION_JSON} does not exist.")
            dict_telemetry = {}

        if self.timestamp:
            timestamp = self.timestamp.isoformat()
        else:
            timestamp = datetime.datetime.now().isoformat()
        new_telemetry_entry = self.model_dump(exclude={"timestamp"})
        dict_telemetry[timestamp] = new_telemetry_entry
        json_telemetry = json.dumps(dict_telemetry, indent=4, sort_keys=True)

        async with async_open(con.TELEMETRY_LOCATION_JSON, "w") as afp:
            # logger.debug(f"Writing to {con.TELEMETRY_LOCATION_JSON}")
            await afp.write(str(json_telemetry))
        logger.debug("Observation stored")

    def model_post_init(self, __context__: Any) -> None:
        """
        Initializes the telemetry model and triggers CSV storage.

        Args:
            __context__ (Any): Context data passed during initialization.

        Returns:
            None
        """
        loop = asyncio.get_event_loop()
        loop.create_task(self.store_observation_csv())
