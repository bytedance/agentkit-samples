# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

logger = logging.getLogger(__name__)

DEFAULT_BUCKET = "video_generation_output"
DEFAULT_REGION = "ap-southeast-1"

DEFAULT_ARK_API_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3"

DEFAULT_MODEL_AGENT_NAME = "deepseek-v4-pro-260425"
DEFAULT_MODEL_AGENT_API_BASE = DEFAULT_ARK_API_BASE

DEFAULT_VIDEO_MODEL_NAME = "dreamina-seedance-2-5-260628"
DEFAULT_VIDEO_MODEL_API_BASE = DEFAULT_ARK_API_BASE

DEFAULT_IMAGE_GENERATE_MODEL_NAME = "dola-seedream-5-0-pro-260628"
DEFAULT_IMAGE_GENERATE_MODEL_API_BASE = DEFAULT_ARK_API_BASE


# Directories searched for a `.env` file, highest priority first. The current
# working directory is always searched last.
_ENV_FILE_DIRS = [Path(__file__).resolve().parent]


def load_env_file() -> list[Path]:
    """Load environment variables from `.env` files (optional).

    Precedence: values in a `.env` file win over variables already exported in
    the shell; anything not present in any `.env` file falls back to the shell
    environment. Files are searched in `_ENV_FILE_DIRS` and then the current
    working directory; when several exist, the earlier (project-side) file wins
    for keys they share. Missing files are ignored.

    Returns the list of `.env` files that were loaded.
    """
    loaded: list[Path] = []
    seen: set[Path] = set()
    for directory in [*_ENV_FILE_DIRS, Path.cwd()]:
        env_file = (directory / ".env").resolve()
        if env_file in seen or not env_file.is_file():
            continue
        seen.add(env_file)
        loaded.append(env_file)

    merged: dict[str, str] = {}
    # Apply lowest-priority (CWD) first so higher-priority files override it.
    for env_file in reversed(loaded):
        merged.update(
            {k: v for k, v in dotenv_values(env_file).items() if v is not None}
        )
    os.environ.update(merged)

    for env_file in loaded:
        logger.info(f"[consts] Loaded environment variables from {env_file}")
    return loaded


def refresh_veadk_model_settings() -> None:
    """Rebuild veadk's model settings from the current environment.

    veadk snapshots its model configuration into the `veadk.config.settings`
    singleton the first time `veadk.config` is imported, and resolves the
    ModelArk endpoint (BytePlus vs. Volcano Engine, off CLOUD_PROVIDER) at that
    same moment. `veadk web` imports veadk *before* it loads this agent, so
    that snapshot predates everything set above: `Agent.model_api_base`
    defaults to `settings.model.api_base` and would silently keep veadk's
    built-in mainland endpoint, ignoring MODEL_AGENT_API_BASE. A BytePlus ARK
    key sent there fails with `401 AuthenticationError: The API key doesn't
    exist`.

    Rebuilding `settings.model` re-reads every MODEL_AGENT_* variable, so the
    environment wins as documented. This is a no-op when veadk has not been
    imported yet: it then builds its settings from the environment anyway.
    """
    veadk_config = sys.modules.get("veadk.config")
    if veadk_config is None:
        return
    settings = veadk_config.settings
    settings.model = type(settings.model)()
    logger.info(
        f"[consts] Rebuilt veadk model settings, api_base={settings.model.api_base}"
    )


def set_veadk_environment_variables():
    # veadk keys its BytePlus behavior off CLOUD_PROVIDER, not the
    # AGENTKIT_CLOUD_PROVIDER variable the agentkit SDK reads: with
    # CLOUD_PROVIDER=byteplus, veadk switches its own endpoint/model defaults
    # to BytePlus and maps BYTEPLUS_ACCESS_KEY/BYTEPLUS_SECRET_KEY onto the
    # VOLCENGINE_* variables it uses internally (veadk/config.py). veadk
    # snapshots all of this when first imported, so this function must run
    # before any veadk import.
    # Load `.env` first (project dir, then CWD); its values override the shell.
    load_env_file()

    os.environ.setdefault(
        "CLOUD_PROVIDER", os.getenv("AGENTKIT_CLOUD_PROVIDER", "byteplus")
    )

    os.environ["MODEL_AGENT_NAME"] = os.getenv(
        "MODEL_AGENT_NAME", DEFAULT_MODEL_AGENT_NAME
    )
    os.environ["MODEL_AGENT_API_BASE"] = os.getenv(
        "MODEL_AGENT_API_BASE", DEFAULT_MODEL_AGENT_API_BASE
    )

    os.environ["MODEL_VIDEO_NAME"] = os.getenv(
        "MODEL_VIDEO_NAME", DEFAULT_VIDEO_MODEL_NAME
    )
    os.environ["MODEL_VIDEO_API_BASE"] = os.getenv(
        "MODEL_VIDEO_API_BASE", DEFAULT_VIDEO_MODEL_API_BASE
    )

    os.environ["MODEL_IMAGE_NAME"] = os.getenv(
        "MODEL_IMAGE_NAME", DEFAULT_IMAGE_GENERATE_MODEL_NAME
    )
    os.environ["MODEL_IMAGE_API_BASE"] = os.getenv(
        "MODEL_IMAGE_API_BASE", DEFAULT_IMAGE_GENERATE_MODEL_API_BASE
    )

    # The variables above only reach the agent if veadk re-reads them; see
    # refresh_veadk_model_settings().
    refresh_veadk_model_settings()
