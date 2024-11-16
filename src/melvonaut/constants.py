"""
System constant values

:author: Jonathan Decker
"""

LOG_LOCATION = "logs/melvonaut/melvonaut_{time:YYYY-MM-DD_HH}.log"

BASE_URL = "http://10.100.10.11:33000/"

OBJECTIVE_ENDPOINT = f"{BASE_URL}objective"
ANNOUNCEMENTS_ENDPOINT = f"{BASE_URL}announcements"
OBSERVATION_ENDPOINT = f"{BASE_URL}observation"
CONTROL_ENDPOINT = f"{BASE_URL}control"
IMAGE_ENDPOINT = f"{BASE_URL}image"
BEACON_ENDPOINT = f"{BASE_URL}beacon"
