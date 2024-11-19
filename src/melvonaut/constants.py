"""
System constant values

:author: Jonathan Decker
"""
# TODO zum teil into shared moven

LOG_LOCATION = "logs/melvonaut/log_melvonaut_{time:YYYY-MM-DD_HH}.log"
TELEMETRY_LOCATION = "logs/melvonaut/telemetry_melvonaut.json"
IMAGE_PATH = "logs/melvonaut/images/"
IMAGE_LOCATION = (
    IMAGE_PATH
    + "image_melvonaut_angle_{angle}_x_{cor_x}_y_{cor_y}_{time}.png"
)

BASE_URL = "http://10.100.10.11:33000/"

OBJECTIVE_ENDPOINT = f"{BASE_URL}objective"
ANNOUNCEMENTS_ENDPOINT = f"{BASE_URL}announcements"
OBSERVATION_ENDPOINT = f"{BASE_URL}observation"
CONTROL_ENDPOINT = f"{BASE_URL}control"
IMAGE_ENDPOINT = f"{BASE_URL}image"
BEACON_ENDPOINT = f"{BASE_URL}beacon"

OBSERVATION_REFRESH_RATE = 5  # Seconds between observation requests

STATE_TRANSITION_TIME = 3 * 60  # Seconds for regular state transitions
STATE_TRANSITION_TO_SAFE_TIME = 1 * 60  # Seconds for state transitions to safe
STATE_TRANSITION_FROM_SAFE_TIME = 20 * 60  # Seconds for state transitions from safe

BATTERY_LOW_THRESHOLD = 25
BATTERY_HIGH_THRESHOLD = 0  # Difference to Max Battery before switching
