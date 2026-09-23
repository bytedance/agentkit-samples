"""Installation-bound endpoints; process environment cannot switch the package."""

import json
from pathlib import Path

# Required package data. A missing or invalid file must not fall back to production.
CONFIG = json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))
NAME = CONFIG["environment"]
API_ENDPOINT = CONFIG["api_endpoint"]
SIGNIN_ENDPOINT = CONFIG["signin_endpoint"]
STS_ENDPOINT = CONFIG["sts_endpoint"]
CONSOLE_URL = CONFIG["console_url"]
REGION = CONFIG["region"]
HEADERS = CONFIG["headers"]
UPLOAD_HOSTS = CONFIG["upload_hosts"]
IMAGEX_ENDPOINT = CONFIG["imagex_endpoint"]
IMAGEX_SERVICE_ID = CONFIG["imagex_service_id"]
AUTH_HOME_PREFIX = "volcengine-sms-{}-auth-".format(NAME)
