# Folder structure
from os import cpu_count
from shared.models import CameraAngle

MEL_LOG_LOCATION = "logs/melvonaut/log_melvonaut_{time:YYYY-MM-DD_HH}.log"
PANORAMA_PATH = "media/"
TELEMETRY_LOCATION_JSON = "logs/melvonaut/telemetry_melvonaut.json"
TELEMETRY_LOCATION_CSV = "logs/melvonaut/telemetry_melvonaut.csv"
IMAGE_PATH = "logs/melvonaut/images/"
IMAGE_LOCATION = IMAGE_PATH + "image_{melv_id}_{angle}_{time}_x_{cor_x}_y_{cor_y}.png"

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

# world map
WORLD_X = 21600
WORLD_Y = 10800

ACCELERATION = 0.04

# Our settings, could be changed later
OBSERVATION_REFRESH_RATE = 5  # Seconds between observation requests
BATTERY_LOW_THRESHOLD = 20
BATTERY_HIGH_THRESHOLD = 0  # Difference to Max Battery before switching

TARGET_ANGLE_DEG = 23
# With total speed over 50, cannot use wide angle camera
# 49.9 = y + x
# x = 2.35585 * y
# 49.9 = 2.35585 * y + y
# 49.9 = 3.35585 * y
# y = 49.9 / 3.35585
# y = 14.87
# 49.9 - 14.87 = 35.03 = x
TARGET_SPEED_NORMAL_X = 35.03  # 2.35585 times as much as Y
TARGET_SPEED_NORMAL_Y = 14.87

# With total speed over 10, cannot use narrow angle camera
# 9.9 = y + x
# y = 9.9 / 3.35585
# y = 2.95
# 9.9 - 2.95 = 6.95 = x
TARGET_SPEED_NARROW_X = 6.95
TARGET_SPEED_NARROW_Y = 2.95

# Total speed can be up to 71
# 71 = y + x
# y = 71 / 3.35585
# y = 21.16
# 71 - 21.16 = 49.84 = x
TARGET_SPEED_WIDE_X = 49.84
TARGET_SPEED_WIDE_Y = 21.16

DISTANCE_BETWEEN_IMAGES = 250  # How many pixel before taking another image

TARGET_CAMERA_ANGLE_ACQUISITION = CameraAngle.Wide
RIFT_LOG_LEVEL = "INFO"

TRACING = False


## For image processing
NUMBER_OF_WORKER_THREADS = cpu_count() - 2      # use 1 for single core
DO_IMAGE_NUDGING_SEARCH = False         # if False ignore SEARCH_GRID_SIDE_LENGTH
SEARCH_GRID_SIDE_LENGTH = 15                    # should be uneven

# should be 8, only for old datasets can be 10
IMAGE_NAME_UNDERSCORE_COUNT = 9
# should be 2, only for old datasets can be 3, since files were named differently back then
IMAGE_ANGLE_POSITION = 3

# save the curent panaoma each X images
SAVE_PANAORMA_STEP = 1000
