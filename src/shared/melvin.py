
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

class Camera_Angle(StrEnum):
    Wide = "wide"
    Narrow = "narrow"
    Normal = "normal"
    Unknown = "unknown"

class Melvin():
    active_time: float
    angle: Camera_Angle
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

    old_pos: tuple[int,int]
    older_pos: tuple[int,int]
    oldest_pos: tuple[int,int]
    last_timestamp: datetime.datetime

    pre_transition_state: State
    planed_transition_state: State

    def __init__(self):
        self.fuel = 100
        self.battery = 100
        self.sate = State.Unknown
        self.active_time = -1
        self.angle = Camera_Angle.Unknown
    
        self.width_x = -1
        self.height_y = -1
        self.vx = -1
        self.vy = -1
        self.simulation_speed = 1

        self.old_pos = (-1,-1)
        self.older_pos = (-1,-1)
        self.oldest_pos = (-1,-1)
        self.last_timestamp = datetime.datetime.now(datetime.timezone.utc)
        self.pre_transition_state = State.Unknown
        self.planed_transition_state = State.Unknown

        

    def reset(self):
        try:
            response  = requests.get(RESET_ENDPOINT)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            data = f"HTTP Error in reset(): {e}"

        self.update_telemetry()

    def update_telemetry(self):
        #print("A")
        try:
            response  = requests.get(OBSERVATION_ENDPOINT)
            response.raise_for_status()
            
            data = response.json()
        except requests.exceptions.RequestException as e:
            data = f"HTTP Error in update_telemetry(): {e}"
            return

        # TODO check if data is valid
        print(data)

        self.active_time = data['active_time']
        self.battery = data['battery']
        self.fuel = data['fuel']
        self.state = data['state']
        self.width_x = data['width_x']
        self.height_y = data['height_y']
        self.vx = data['vx']
        self.vy = data['vy']
        self.simulation_speed = data['simulation_speed']
        self.timestamp = datetime.datetime.fromisoformat(data['timestamp'])
        self.angle = data['angle']

        # if the last timestamp is longer then 10s ago shift arroun
        if (self.timestamp - self.last_timestamp).total_seconds() > 10:
            self.last_timestamp = self.timestamp
            self.oldest_pos = self.older_pos
            self.older_pos = self.old_pos
            self.old_pos = (self.width_x, self.height_y)
        
        self.sate = data['state']
        if self.state != State.Transition:
            self.planed_transition_state = State.Unknown
        #    self.pre_transition_state = self.state
        """
        print(self.timestamp)
        print(self.last_timestamp)
        print(self.old_pos)
        print(self.older_pos)
        print(self.oldest_pos)
        """
        print("done")
        return "updated Telemetry"
    

    def change_simulationspeed(self, user_speed_multiplier):
        params = {
            "is_network_simulation": "false",
            "user_speed_multiplier": user_speed_multiplier
        }
        try:
            response  = requests.put(SIMULATION_ENDPOINT, params=params)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            data = f"HTTP Error in change_simulationspeed: {e}"

        if response.status_code == 200:
            print("Changed simulation_speed")
        else:
            print("Simulation Speed change failed")

        return

    # only change the state, nothing else
    def change_state(self, target_state):
        body = {
            'vel_x': self.vx,
            'vel_y': self.vy,
            'camera_angle': self.angle,
            'state': str(target_state)
        }
        
        self.pre_transition_state = self.state
        try:
            response  = requests.put(CONTROL_ENDPOINT, json=body)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            data = f"HTTP Error in change_state(): {e}"

        self.planed_transition_state = target_state
        print("Changed to: " + target_state)
        self.update_telemetry()
        return