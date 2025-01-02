# Folder structure
from os import cpu_count
from shared.models import CameraAngle

import datetime

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
# Scaled down version for thumbnail
SCALED_WORLD_X = 1080
SCALED_WORLD_Y = 540

# While in Stitching add this border in each direction
STITCHING_BORDER = 1000

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

DISTANCE_BETWEEN_IMAGES = 350  # How many pixel before taking another image

RIFT_LOG_LEVEL = "INFO"

TRACING = False


## For image processing
NUMBER_OF_WORKER_THREADS = cpu_count() - 2  # use 1 for single core
DO_IMAGE_NUDGING_SEARCH = False  # if False ignore SEARCH_GRID_SIDE_LENGTH
SEARCH_GRID_SIDE_LENGTH = 15  # should be uneven

# should be false, the naming convenction for images changed, for all new images this should be false
USE_LEGACY_IMAGE_NAMES = False
# should be 8, only for old datasets can be 9
IMAGE_NAME_UNDERSCORE_COUNT = 8
# should be 2, only for old datasets can be 3, since files were named differently back then
IMAGE_ANGLE_POSITION = 2

# save the curent panaoma each X images
SAVE_PANAORMA_STEP = 1000

# see image_processing:count_matching_pixels. Images are (0-255,0-255,0-255), summed up over RGB how
# difference two pixels are allowed to be to still count as matching
IMAGE_NOISE_FORGIVENESS = 20

# WIP
# first version sorted images by time, this flag instead sorts by position, starting in the top-right corner
IMAGE_ITERATION_POSITION_NOT_TIME = True
# only stiched that many images for better testing
STITCHING_COUNT_LIMIT = 3000

## [MANUAL CONTROL]
TARGET_CAMERA_ANGLE_ACQUISITION = CameraAngle.Narrow
# To solve a single objective, set a time window in which melvonaut is active
start_time = datetime.datetime(2025, 1, 2, 13, 00, tzinfo=datetime.timezone.utc)
stop_time = datetime.datetime(2025, 1, 3, 12, 00, tzinfo=datetime.timezone.utc)
