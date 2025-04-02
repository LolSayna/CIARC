from os import cpu_count

RIFT_LOG_LEVEL = "INFO"

# [PATHS]
MEL_LOG_PATH = "logs/melvonaut/"
MEL_LOG_FORMAT = "log_melvonaut_{time:YYYY-MM-DD_HH}.log"
MEL_LOG_LOCATION = MEL_LOG_PATH + MEL_LOG_FORMAT
TELEMETRY_LOCATION_JSON = "logs/melvonaut/telemetry_melvonaut.json"
TELEMETRY_LOCATION_CSV = "logs/melvonaut/telemetry_melvonaut.csv"
EVENT_LOCATION_CSV = "logs/melvonaut/event_melvonaut.csv"
IMAGE_PATH_BASE = "logs/melvonaut/images/"
IMAGE_PATH = "logs/melvonaut/images/"
IMAGE_LOCATION = IMAGE_PATH + "image_{melv_id}_{angle}_{time}_x_{cor_x}_y_{cor_y}.png"
RIFT_LOG_LOCATION = "logs/rift_console/log_rift-console_{time:YYYY-MM-DD_HH}.log"
PANORAMA_PATH = "media/"
CONSOLE_LOG_PATH = "logs/rift_console/"
CONSOLE_FROM_MELVONAUT_PATH = "logs/rift_console/from_melvonaut/"
CONSOLE_LIVE_PATH = "logs/rift_console/images/live/"
CONSOLE_DOWNLOAD_PATH = "logs/rift_console/images/download/"
CONSOLE_STICHED_PATH = "logs/rift_console/images/stitched/"
CONSOLE_EBT_PATH = "logs/rift_console/images/ebt/"
MEL_PERSISTENT_SETTINGS = "logs/melvonaut/persistent_settings.json"

# [URLs]
BASE_URL = "http://10.100.10.11:33000/"  # URL of our instance
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
SLOTS_ENDPOINT = f"{BASE_URL}slots"
ACHIEVEMENTS_ENDPOINT = f"{BASE_URL}achievements"
DAILYMAP_ENDPOINT = f"{BASE_URL}dailyMap"

# [From User Manual]
STATE_TRANSITION_TIME = 3 * 60  # Seconds for regular state transitions
STATE_TRANSITION_TO_SAFE_TIME = 1 * 60  # Seconds for state transitions to safe
STATE_TRANSITION_FROM_SAFE_TIME = 20 * 60  # Seconds for state transitions from safe
WORLD_X = 21600
WORLD_Y = 10800
ACCELERATION = 0.02


# [Console]
# Since images get very large (>400MB) a smaller 2nd version is displayed
THUMBNAIL_X = 1000
THUMBNAIL_Y = 500
# Calculate trajektorie
TRAJ_TIME = 3600 * 12  # generate points up to 12 hours
TRAJ_STEP = 10  # merge 10s into 1 point
# How many images should be shown at once in the image viewer tabs
CONSOLE_IMAGE_VIEWER_LIMIT = 1000

## [Image Processing]
STITCHING_BORDER = 1000  # While in Stitching add this border in each direction
NUMBER_OF_WORKER_THREADS = (cpu_count() or 4) - 2  # use 1 for single core
SAVE_PANORAMA_STEP = 1000  # save the current panorama each X images
STITCHING_COUNT_LIMIT = 5000  # stitching limit
# Toogle between sorted/stitching images by position, starting in the top-right corner
# else sort by timestamp
SORT_IMAGE_BY_POSITION = True
# The naming convention for images changed, can be changed for legacy data
USE_LEGACY_IMAGE_NAMES = False  # should be false, only true for older datasets
IMAGE_NAME_UNDERSCORE_COUNT = 8  # should be 8, only for old datasets can be 9
IMAGE_ANGLE_POSITION = 2  # hould be 2, only for old datasets can be 3

## [New stitching algorithm]
# Activate an improved stitching algorithm, which tries different placements of each image, but
# takes a very long run time. Works, but needs further refinement
DO_IMAGE_NUDGING_SEARCH = False  # if False ignore SEARCH_GRID_SIDE_LENGTH
SEARCH_GRID_SIDE_LENGTH = 15  # should be uneven
# see image_processing:count_matching_pixels. Images are (0-255,0-255,0-255), summed up over RGB how
# difference two pixels are allowed to be to still count as matching
IMAGE_NOISE_FORGIVENESS = 20
