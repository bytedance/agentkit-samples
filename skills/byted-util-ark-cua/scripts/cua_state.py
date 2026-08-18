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

"""Local caches for the AgentPlan CUA Skill CLI.

`AuthState` stores the API base URL, user identity, and AgentPlan API key in
a 0600 file at ~/.openclaw/ark-cua/auth.json (override with
AP_CUA_SKILL_AUTH_FILE).
`SessionState` remembers the last invocation id so weak agents can run
`watch --last`. Permissions are repaired automatically; if repair fails the CLI
refuses to continue so credentials are never left world-readable.
"""

import json
import os
import stat
import tempfile
from pathlib import Path

from cua_util import SkillError

DEFAULT_DIR = Path.home() / ".openclaw" / "ark-cua"
DEFAULT_AUTH_FILE = DEFAULT_DIR / "auth.json"
DEFAULT_SESSION_FILE = DEFAULT_DIR / "session.json"


def auth_file_path():
    override = os.environ.get("AP_CUA_SKILL_AUTH_FILE") or os.environ.get("CUA_SKILL_AUTH_FILE")
    return Path(override).expanduser() if override else DEFAULT_AUTH_FILE


def session_file_path():
    override = os.environ.get("AP_CUA_SKILL_SESSION_FILE") or os.environ.get("CUA_SKILL_SESSION_FILE")
    if override:
        return Path(override).expanduser()
    return auth_file_path().parent / "session.json"


class _JsonFile:
    """A 0600 JSON file with atomic writes and permission repair."""

    def __init__(self, path, data):
        self.path = path
        self.data = data

    @classmethod
    def load(cls, path):
        if not path.exists():
            return cls(path, {})
        _ensure_secure_permissions(path)
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SkillError("INTERNAL", f"Cannot read {path}: {exc}")
        data = json.loads(raw) if raw.strip() else {}
        if not isinstance(data, dict):
            raise SkillError("INTERNAL", f"{path} is corrupted; run auth login again")
        return cls(path, data)

    def save(self):
        path = self.path
        try:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(self.data, handle, ensure_ascii=False, indent=2)
                os.chmod(tmp, 0o600)
                os.replace(tmp, path)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        except OSError as exc:
            raise SkillError("INTERNAL", f"Cannot persist {path}: {exc}")


class AuthState(_JsonFile):
    @classmethod
    def load(cls):
        return super().load(auth_file_path())

    @property
    def api_base_url(self):
        return self.data.get("api_base_url")

    @property
    def access_token(self):
        # Keep the property name for the shared CLI code: in the AgentPlan
        # variant the bearer token is the user's Ark/AgentPlan API key.
        return self.data.get("api_key")

    @property
    def refresh_token(self):
        return None

    @property
    def access_token_expires_at(self):
        return self.data.get("access_token_expires_at")

    @property
    def desktop_bound(self):
        return bool(self.data.get("desktop_bound"))

    @property
    def user(self):
        return self.data.get("user") or {}

    def set_api_base_url(self, base_url):
        self.data["api_base_url"] = base_url
        self.save()

    def set_tokens(self, *, api_base_url, user, access_token, access_token_expires_at,
                   refresh_token, refresh_token_expires_at, desktop_bound):
        self.data.update({
            "api_base_url": api_base_url,
            "user": user,
            "api_key": access_token,
            "access_token_expires_at": access_token_expires_at,
            "desktop_bound": desktop_bound,
        })
        self.save()

    def set_api_key(self, *, api_base_url, api_key, user=None, desktop_bound=False):
        self.data.update({
            "api_base_url": api_base_url,
            "api_key": api_key,
            "user": user or {},
            "desktop_bound": bool(desktop_bound),
        })
        for key in ("access_token", "access_token_expires_at", "refresh_token",
                    "refresh_token_expires_at"):
            self.data.pop(key, None)
        self.save()

    def clear_tokens(self):
        for key in ("api_key", "access_token", "access_token_expires_at", "refresh_token",
                    "refresh_token_expires_at", "user", "desktop_bound"):
            self.data.pop(key, None)
        self.save()


class SessionState(_JsonFile):
    @classmethod
    def load(cls):
        return super().load(session_file_path())

    @property
    def last_invocation_id(self):
        return self.data.get("last_invocation_id")

    def set_last_invocation_id(self, invocation_id):
        if not invocation_id:
            return
        self.data["last_invocation_id"] = invocation_id
        self.save()

    # The semantic command surface (task/context/artifact) remembers the
    # most recent id of each kind so weak agents can use `--last-*` instead of
    # threading ids through every call.
    @property
    def last_task_id(self):
        # A task is backed by an invocation; they share the same id space.
        return self.data.get("last_task_id") or self.data.get("last_invocation_id")

    @property
    def last_context_id(self):
        return self.data.get("last_context_id")

    @property
    def last_artifact_id(self):
        return self.data.get("last_artifact_id")

    def set_last(self, **ids):
        """Persist the provided non-empty task, context, artifact, or invocation ids."""
        changed = False
        for key in ("last_task_id", "last_context_id", "last_artifact_id", "last_invocation_id"):
            value = ids.get(key)
            if value and self.data.get(key) != value:
                self.data[key] = value
                changed = True
        if changed:
            self.save()


def _ensure_secure_permissions(path):
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            os.chmod(path, 0o600)
            if stat.S_IMODE(path.stat().st_mode) & 0o077:
                raise SkillError("INTERNAL", f"{path} has unsafe permissions and could not be repaired")
    except OSError as exc:
        raise SkillError("INTERNAL", f"Cannot inspect {path}: {exc}")
