
import datetime
from enum import StrEnum
import requests
from shared.constants import *

class State(StrEnum):
    Deployment = "deployment"
    Acquisition = "acquisition"
    Charge = "charge"
    Safe = "safe"
    Communication = "communication"
    Transition = "transition"
    Unknown = "none"

class Melvin():
    active_time: float
    battery: float
    distance_covered: float
    fuel: float
    width_x: float
    height_y: float
    images_taken: int
    max_battery: float
    objectives_done: int
    objectives_points: int
    simulation_speed: int
    state: State
    timestamp: datetime.datetime
    vx: float
    vy: float
    def __init__(self):
        self.fuel = 100
        self.battery = 100
        self.sate = State.Unknown
        self.active_time = -1
    
        self.width_x = -1
        self.height_y = -1

    def update_telemtry(self):
        try:
            response  = requests.get(OBSERVATION_ENDPOINT)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            data = f"Error fetching data: {e}"

        self.active_time = data['active_time']
        self.battery = data['battery']
        self.fuel = data['fuel']
        self.state = data['state']
        self.width_x = data['width_x']
        self.height_y = data['height_y']

        return "updated Telemetry"