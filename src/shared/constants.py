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
MEL_PERSISTENT_SETTINGS = "logs/melvonaut/persistent_settings.json"

# [TRAJECTORY]
# Number of seconds to calculate the path
TRAJ_TIME = 3600

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

# While in Stitching add this border in each direction
STITCHING_BORDER = 1000
## For image processing
NUMBER_OF_WORKER_THREADS = cpu_count() - 2  # use 1 for single core
DO_IMAGE_NUDGING_SEARCH = False  # if False ignore SEARCH_GRID_SIDE_LENGTH
SEARCH_GRID_SIDE_LENGTH = 15  # should be uneven

# should be false, the naming convention for images changed, for all new images this should be false
USE_LEGACY_IMAGE_NAMES = False
# should be 8, only for old datasets can be 9
IMAGE_NAME_UNDERSCORE_COUNT = 8
# should be 2, only for old datasets can be 3, since files were named differently back then
IMAGE_ANGLE_POSITION = 2

# save the current panorama each X images
SAVE_PANORAMA_STEP = 1000

# see image_processing:count_matching_pixels. Images are (0-255,0-255,0-255), summed up over RGB how
# difference two pixels are allowed to be to still count as matching
IMAGE_NOISE_FORGIVENESS = 20

# WIP
# first version sorted images by time, this flag instead sorts by position, starting in the top-right corner
IMAGE_ITERATION_POSITION_NOT_TIME = True
# only stitched that many images for better testing
STITCHING_COUNT_LIMIT = 5000
