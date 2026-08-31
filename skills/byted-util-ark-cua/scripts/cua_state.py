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
import time
import uuid
from pathlib import Path

from cua_util import SkillError

DEFAULT_DIR = Path.home() / ".openclaw" / "ark-cua"
DEFAULT_AUTH_FILE = DEFAULT_DIR / "auth.json"
DEFAULT_SESSION_FILE = DEFAULT_DIR / "session.json"


def _credential_state_key(environment_id, *parts):
    """Build a collision-safe key for environment-isolated Credential state."""
    environment = str(environment_id or "").strip().lower()
    if environment != "prod":
        raise SkillError(
            "VALIDATION_ERROR",
            "Credential session state requires the production environment.",
        )
    return json.dumps(
        [environment, *(str(part or "") for part in parts)],
        ensure_ascii=False,
        separators=(",", ":"),
    )


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
    def credential_source(self):
        return self.data.get("credential_source")

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
        self.data.pop("credential_source", None)
        self.save()

    def set_api_key(self, *, api_base_url, api_key, user=None, desktop_bound=False,
                    credential_source=None):
        self.data.update({
            "api_base_url": api_base_url,
            "api_key": api_key,
            "user": user or {},
            "desktop_bound": bool(desktop_bound),
        })
        if credential_source:
            self.data["credential_source"] = credential_source
        for key in ("access_token", "access_token_expires_at", "refresh_token",
                    "refresh_token_expires_at"):
            self.data.pop(key, None)
        self.save()

    def clear_tokens(self):
        for key in ("api_key", "credential_source", "access_token", "access_token_expires_at",
                    "refresh_token", "refresh_token_expires_at", "user", "desktop_bound"):
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

    def credential_begin_request(self, environment_id, desktop_id, mode):
        key = _credential_state_key(environment_id, desktop_id or "default", mode)
        pending = self.data.get("credential_begin_requests")
        if not isinstance(pending, dict):
            pending = {}
        item = pending.get(key)
        if isinstance(item, dict) and int(item.get("expires_at") or 0) > int(time.time()):
            request_id = str(item.get("request_id") or "").strip()
            if request_id:
                return request_id
        request_id = "cred-" + uuid.uuid4().hex
        pending[key] = {"request_id": request_id, "expires_at": int(time.time()) + 3600}
        self.data["credential_begin_requests"] = pending
        self.save()
        return request_id

    def renew_expired_credential_begin_request(
        self, environment_id, desktop_id, mode, expected_request_id
    ):
        """Replace only the pending begin id the server proved is expired."""
        key = _credential_state_key(environment_id, desktop_id or "default", mode)
        pending = self.data.get("credential_begin_requests")
        if not isinstance(pending, dict):
            pending = {}
        item = pending.get(key)
        current_request_id = str(
            item.get("request_id") if isinstance(item, dict) else ""
        ).strip()
        if current_request_id and current_request_id != expected_request_id:
            return current_request_id
        request_id = "cred-" + uuid.uuid4().hex
        pending[key] = {"request_id": request_id, "expires_at": int(time.time()) + 3600}
        self.data["credential_begin_requests"] = pending
        self.save()
        return request_id

    def complete_credential_begin(
        self, environment_id, desktop_id, mode, workflow_id, device_id=None
    ):
        key = _credential_state_key(environment_id, desktop_id or "default", mode)
        pending = self.data.get("credential_begin_requests")
        if isinstance(pending, dict):
            pending.pop(key, None)
            self.data["credential_begin_requests"] = pending
        workflows = self.data.get("credential_workflows")
        if not isinstance(workflows, dict):
            workflows = {}
        workflows[_credential_state_key(environment_id, workflow_id)] = {
            "environment_id": environment_id,
            "desktop_id": desktop_id or "",
            "mode": mode,
            "updated_at": int(time.time()),
        }
        self.data["credential_workflows"] = workflows
        if device_id:
            devices = self.data.get("credential_devices")
            if not isinstance(devices, dict):
                devices = {}
            devices[_credential_state_key(environment_id, desktop_id or "default")] = device_id
            self.data["credential_devices"] = devices
        self.save()

    def credential_device(self, environment_id, desktop_id):
        devices = self.data.get("credential_devices")
        key = _credential_state_key(environment_id, desktop_id or "default")
        return devices.get(key) if isinstance(devices, dict) else None

    def credential_reset_request(self, environment_id, desktop_id, device_id):
        key = _credential_state_key(environment_id, desktop_id, device_id)
        resets = self.data.get("credential_reset_requests")
        if not isinstance(resets, dict):
            resets = {}
        current = resets.get(key)
        request_id = str(current.get("request_id") if isinstance(current, dict) else current or "").strip()
        if not request_id:
            request_id = "cred-reset-" + uuid.uuid4().hex
            resets[key] = {"request_id": request_id, "central_revoked": False}
            self.data["credential_reset_requests"] = resets
            self.save()
        return request_id

    def credential_reset_central_revoked(self, environment_id, desktop_id, device_id):
        resets = self.data.get("credential_reset_requests")
        key = _credential_state_key(environment_id, desktop_id, device_id)
        item = resets.get(key) if isinstance(resets, dict) else None
        return isinstance(item, dict) and item.get("central_revoked") is True

    def mark_credential_reset_central_revoked(self, environment_id, desktop_id, device_id):
        key = _credential_state_key(environment_id, desktop_id, device_id)
        resets = self.data.get("credential_reset_requests")
        if not isinstance(resets, dict):
            resets = {}
        item = resets.get(key)
        if not isinstance(item, dict):
            item = {"request_id": str(item or "cred-reset-" + uuid.uuid4().hex)}
        item["central_revoked"] = True
        resets[key] = item
        self.data["credential_reset_requests"] = resets
        self.save()

    def finish_credential_reset(self, environment_id, desktop_id, device_id):
        resets = self.data.get("credential_reset_requests")
        if isinstance(resets, dict):
            resets.pop(_credential_state_key(environment_id, desktop_id, device_id), None)
            self.data["credential_reset_requests"] = resets
        devices = self.data.get("credential_devices")
        if isinstance(devices, dict):
            devices.pop(
                _credential_state_key(environment_id, desktop_id or "default"), None
            )
            self.data["credential_devices"] = devices
        self.save()

    def remember_credential_operation(self, environment_id, operation_id, workflow_id):
        operations = self.data.get("credential_operations")
        if not isinstance(operations, dict):
            operations = {}
        operations[_credential_state_key(environment_id, operation_id)] = workflow_id
        self.data["credential_operations"] = operations
        self.save()

    def workflow_for_credential_operation(self, environment_id, operation_id):
        operations = self.data.get("credential_operations")
        key = _credential_state_key(environment_id, operation_id)
        return operations.get(key) if isinstance(operations, dict) else None

    def finish_credential_workflow(self, environment_id, workflow_id):
        workflow_key = _credential_state_key(environment_id, workflow_id)
        environment_prefix = workflow_key.split(",", 1)[0] + ","
        workflows = self.data.get("credential_workflows")
        if isinstance(workflows, dict):
            workflows.pop(workflow_key, None)
            self.data["credential_workflows"] = workflows
        operations = self.data.get("credential_operations")
        if isinstance(operations, dict):
            self.data["credential_operations"] = {
                key: value
                for key, value in operations.items()
                if not (key.startswith(environment_prefix) and value == workflow_id)
            }
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
