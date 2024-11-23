# Folder structure
MEL_LOG_LOCATION = "logs/melvonaut/log_melvonaut_{time:YYYY-MM-DD_HH}.log"
TELEMETRY_LOCATION = "logs/melvonaut/telemetry_melvonaut.json"
IMAGE_PATH = "logs/melvonaut/images/"
IMAGE_LOCATION = (
    IMAGE_PATH + "image_melvonaut_angle_{angle}_x_{cor_x}_y_{cor_y}_{time}.png"
)

RIFT_LOG_LOCATION = "logs/rift_console/log_rift-console_{time:YYYY-MM-DD_HH}.log"

# URL of our instance
BASE_URL = "http://10.100.10.11:33000/"

# Given Data Reference System API endpoints
OBJECTIVE_ENDPOINT = f"{BASE_URL}objective"
ANNOUNCEMENTS_ENDPOINT = f"{BASE_URL}announcements"
OBSERVATION_ENDPOINT = f"{BASE_URL}observation"
CONTROL_ENDPOINT = f"{BASE_URL}control"
IMAGE_ENDPOINT = f"{BASE_URL}image"
BEACON_ENDPOINT = f"{BASE_URL}beacon"
RESET_ENDPOINT = f"{BASE_URL}reset"
SIMULATION_ENDPOINT = f"{BASE_URL}simulation"
BACKUP_ENDPOINT = f"{BASE_URL}backup"

# From User Manual
STATE_TRANSITION_TIME = 3 * 60  # Seconds for regular state transitions
STATE_TRANSITION_TO_SAFE_TIME = 1 * 60  # Seconds for state transitions to safe
STATE_TRANSITION_FROM_SAFE_TIME = 20 * 60  # Seconds for state transitions from safe

# Our settings, could be changed later
OBSERVATION_REFRESH_RATE = 5  # Seconds between observation requests
BATTERY_LOW_THRESHOLD = 25
BATTERY_HIGH_THRESHOLD = 0  # Difference to Max Battery before switching

TARGET_ANGLE_DEG = 23
TARGET_SPEED_X = 47.117
TARGET_SPEED_Y = 20.0

RIFT_LOG_LEVEL = "DEBUG"
