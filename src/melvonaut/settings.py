# [General Settings]
# Our settings, could be changed later
import datetime

from shared.models import CameraAngle, MELVINTasks

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
TRACING = False

## [Melvin Task Planing]
# Standard mapping, with no objectives and the camera angle below
# CURRENT_MELVIN_TASK: MELVINTasks = MELVINTasks.Mapping
TARGET_CAMERA_ANGLE_ACQUISITION = CameraAngle.Normal

# Automatically do the next upcoming objective
# CURRENT_MELVIN_TASK: MELVINTasks = MELVINTasks.Next_objective

# Do a specific objective
# CURRENT_MELVIN_TASK: MELVINTasks = MELVINTasks.Fixed_objective
# FIXED_OBJECTIVE = "Aurora 10"

# Go for the emergency beacon tracker
CURRENT_MELVIN_TASK: MELVINTasks = MELVINTasks.EBT

# To set a custom time window to be active, or to disable all timing checks
DO_TIMING_CHECK = False
START_TIME = datetime.datetime(2025, 1, 2, 12, 00, tzinfo=datetime.timezone.utc)
STOP_TIME = datetime.datetime(2025, 1, 30, 12, 00, tzinfo=datetime.timezone.utc)
