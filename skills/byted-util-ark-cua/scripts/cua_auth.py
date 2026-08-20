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

"""Authentication orchestration for the AgentPlan CUA Skill CLI.

This skill variant uses the caller's Volcengine Ark AgentPlan API key as the
bearer credential. Keys sourced from arkcli stay in memory; manual fallback
keys are cached locally with 0600 permissions. No key is written to
stdout/stderr. The gateway validates it with Ark acquire and uses the same key
as the model API key for CUA runtime calls.
"""

import contextlib
import getpass
import hmac
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from cua_http import gateway_call, raw_request
from cua_util import RETRYABLE_ERROR_CODES, SkillError, login_setup_command

DEFAULT_LOGIN_TIMEOUT_SEC = 0
ARKCLI_TIMEOUT_SEC = 20
ARKCLI_SKILL_NAME = "byted-util-ark-cua"
ARKCLI_STATE_FILES = ("config.yaml", "profile.yaml", ".env")
ARKCLI_STATE_DIRS = ("identities", "identity_store")


class CredentialHandle:
    """A non-serializable, redacted capability for using one credential."""

    __slots__ = ("_invoke", "source", "profile")

    def __init__(self, value, source, profile=None):
        self._invoke = lambda operation: operation(value)
        self.source = source
        self.profile = profile

    @classmethod
    def optional(cls, value, source, profile=None):
        if not isinstance(value, str) or not value.strip():
            return None
        return cls(value.strip(), source, profile)

    def invoke(self, operation):
        return self._invoke(operation)

    def same_value(self, other):
        if not isinstance(other, CredentialHandle):
            return False
        return self.invoke(
            lambda value: other.invoke(lambda candidate: hmac.compare_digest(value, candidate))
        )

    def __repr__(self):
        return f"CredentialHandle(source={self.source!r}, profile={self.profile!r}, value=<redacted>)"


def authorized_call(state, base_url, method, path, body=None, query=None, timeout=None, retries=0):
    """Call a business endpoint with AgentPlan bearer auth and optional retry.

    `retries` should only be > 0 for idempotent calls (GET, or watch/observe/ping
    which are safe to repeat). Never retry delegate/answer — they create state.
    """
    attempt = 0
    while True:
        try:
            return _authorized_call_once(state, base_url, method, path, body=body, query=query, timeout=timeout)
        except SkillError as exc:
            if exc.code in RETRYABLE_ERROR_CODES and attempt < retries:
                attempt += 1
                time.sleep(min(2 * attempt, 5))
                continue
            raise


def authorized_raw_call(state, base_url, method, path, body=None, query=None, timeout=None, retries=0):
    """Call a business endpoint and return (headers, raw_bytes), with the same
    auth/retry behavior as authorized_call."""
    attempt = 0
    while True:
        try:
            return _authorized_raw_call_once(state, base_url, method, path, body=body, query=query, timeout=timeout)
        except SkillError as exc:
            if exc.code in RETRYABLE_ERROR_CODES and attempt < retries:
                attempt += 1
                time.sleep(min(2 * attempt, 5))
                continue
            raise


def _authorized_call_once(state, base_url, method, path, body=None, query=None, timeout=None):
    kwargs = {"body": body, "query": query}
    if timeout is not None:
        kwargs["timeout"] = timeout
    data, _credential = _with_credential_recovery(
        state,
        lambda token: gateway_call(method, base_url, path, token=token, **kwargs),
    )
    return data


def _authorized_raw_call_once(state, base_url, method, path, body=None, query=None, timeout=None):
    kwargs = {"body": body, "query": query}
    if timeout is not None:
        kwargs["timeout"] = timeout
    result, _credential = _with_credential_recovery(
        state,
        lambda token: raw_request(method, base_url, path, token=token, **kwargs),
    )
    _status, headers, raw = result
    return headers, raw


def login(state, base_url, prompt=True, manual=False, **_unused):
    """Configure and validate an AgentPlan API key."""
    credential = None
    arkcli_discovery = None
    if manual:
        if not prompt or not sys.stdin.isatty():
            raise _auth_required(manual=True)
        credential = CredentialHandle.optional(
            getpass.getpass("AgentPlan API key (manual): "), "manual"
        )
        if not credential:
            raise _auth_required(manual=True)
    else:
        credential, arkcli_discovery = _arkcli_credential()
        if not credential and prompt:
            if not sys.stdin.isatty():
                raise _auth_required(arkcli_discovery)
            credential = CredentialHandle.optional(
                getpass.getpass("AgentPlan API key: "), "prompt"
            )
    if not credential:
        raise _auth_required(arkcli_discovery)

    try:
        data = credential.invoke(
            lambda value: gateway_call("GET", base_url, "/v1/auth/me", token=value)
        )
    except SkillError as exc:
        if credential.source == "arkcli" and _is_agentplan_auth_rejection(exc):
            if not prompt or not sys.stdin.isatty():
                raise _auth_required({"status": "api_key_rejected", "profile": credential.profile})
            credential = CredentialHandle.optional(
                getpass.getpass("AgentPlan API key (arkcli fallback): "), "prompt"
            )
            if not credential:
                raise _auth_required({"status": "api_key_rejected"})
            try:
                data = credential.invoke(
                    lambda value: gateway_call("GET", base_url, "/v1/auth/me", token=value)
                )
            except SkillError as fallback_exc:
                raise _auth_error_with_retry(fallback_exc)
        else:
            raise _auth_error_with_retry(exc, manual=credential.source == "manual")
    user = _safe_user(data.get("user") or data.get("caller") or data)
    # arkcli remains the source of truth. Its key is used only by this process
    # and is deliberately not copied into the CUA auth cache.
    if credential.source != "arkcli":
        credential.invoke(
            lambda value: state.set_api_key(
                api_base_url=base_url,
                api_key=value,
                user=user,
                desktop_bound=bool(data.get("desktop_bound")),
                credential_source=credential.source,
            )
        )
    result = {
        "status": "logged_in",
        "auth_type": "agentplan_api_key",
        "credential_source": credential.source,
        "user": user,
        "desktop_bound": bool(data.get("desktop_bound")),
        "scopes": _scopes(data),
    }
    if credential.profile:
        result["arkcli_profile"] = credential.profile
    return result


def auth_status(state, base_url):
    """Verify the current API key against /v1/auth/me without exposing it."""
    data, credential = _with_credential_recovery(
        state,
        lambda token: gateway_call("GET", base_url, "/v1/auth/me", token=token),
    )
    user = _safe_user(data.get("user") or data.get("caller") or data)
    if user and user != state.user and credential.source in ("cache", "manual"):
        credential.invoke(
            lambda value: state.set_api_key(
                api_base_url=base_url,
                api_key=value,
                user=user,
                desktop_bound=bool(data.get("desktop_bound")),
                credential_source=getattr(state, "credential_source", None),
            )
        )
    result = {
        "status": "logged_in",
        "auth_type": "agentplan_api_key",
        "credential_source": credential.source,
        "api_key_source": credential.source,
        "user": user,
        "scopes": _scopes(data),
        "desktop_bound": bool(data.get("desktop_bound") or state.desktop_bound),
    }
    if credential.profile:
        result["arkcli_profile"] = credential.profile
    return result


def logout(state, base_url):
    state.clear_tokens()
    return {"status": "logged_out"}


# -- internals -------------------------------------------------------------


def _resolve_credential(state):
    source = "manual" if getattr(state, "credential_source", None) == "manual" else "cache"
    cached = CredentialHandle.optional(state.access_token, source)
    if cached:
        return cached, None
    return _arkcli_credential()


def _with_credential_recovery(state, operation):
    credential, discovery = _resolve_credential(state)
    if not credential:
        raise _auth_required(discovery)
    try:
        return credential.invoke(operation), credential
    except SkillError as exc:
        if _is_agentplan_auth_rejection(exc):
            if credential.source == "arkcli":
                raise _auth_required({"status": "api_key_rejected", "profile": credential.profile})
            if credential.source == "manual":
                raise _auth_required(manual=True)
            arkcli_credential, arkcli_discovery = _arkcli_credential()
            if arkcli_credential and not arkcli_credential.same_value(credential):
                try:
                    return arkcli_credential.invoke(operation), arkcli_credential
                except SkillError as arkcli_exc:
                    if _is_agentplan_auth_rejection(arkcli_exc):
                        raise _auth_required({
                            "status": "api_key_rejected",
                            "profile": arkcli_credential.profile,
                        })
                    raise _auth_error_with_retry(arkcli_exc)
            if arkcli_credential:
                raise _auth_required({
                    "status": "api_key_rejected",
                    "profile": arkcli_credential.profile,
                })
            if not arkcli_credential:
                raise _auth_required(arkcli_discovery)
        raise _auth_error_with_retry(exc)


def _arkcli_credential():
    """Read an Agent Plan personal Max key from arkcli without logging it or persisting it."""
    executable = shutil.which("arkcli")
    if not executable:
        return None, {"status": "not_installed"}

    # arkcli is the credential broker. Capture its output only long enough to
    # seal it in a redacted handle; never place it in a result or log record.
    try:
        with _isolated_arkcli_environment() as env:
            return _arkcli_credential_in_environment(executable, env)
    except OSError:
        return None, {"status": "state_snapshot_failed"}


def _arkcli_credential_in_environment(executable, env):
    try:
        listed = subprocess.run(
            [executable, "profile", "list", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=ARKCLI_TIMEOUT_SEC,
            check=False,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return None, {"status": "profile_list_failed"}
    if listed.returncode != 0:
        return None, {"status": _arkcli_error_status(listed.stderr, "profile_list_failed")}
    try:
        payload = json.loads(listed.stdout)
    except (TypeError, ValueError):
        return None, {"status": "invalid_profile_list"}
    profiles = payload.get("profiles") if isinstance(payload, dict) else None
    if not isinstance(profiles, list) and isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        profiles = payload["data"].get("profiles")
    matches = [
        profile for profile in (profiles or [])
        if isinstance(profile, dict)
        and profile.get("type") == "agent-plan"
        and profile.get("plan_tier") == "max"
        and isinstance(profile.get("name"), str)
        and profile["name"].strip()
    ]
    if not matches:
        return None, {"status": "no_agent_plan_max_profile"}
    profile_name = matches[0]["name"].strip()

    # Feed broker stdout directly into the redacted handle. Never assign it to
    # a normal variable or include it in a result or log record.
    try:
        credential = CredentialHandle.optional(
            subprocess.check_output(
                [executable, "profile", "apikey", "get", "--profile", profile_name, "--plain"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=ARKCLI_TIMEOUT_SEC,
                env=env,
            ),
            "arkcli",
            profile_name,
        )
    except (OSError, subprocess.SubprocessError):
        return None, {"status": "apikey_get_failed", "profile": profile_name}
    if not credential:
        return None, {"status": "no_api_key", "profile": profile_name}
    return credential, {"status": "ready", "profile": profile_name}


@contextlib.contextmanager
def _isolated_arkcli_environment():
    """Run read-only arkcli discovery without allowing writes to the real HOME."""
    source_home = Path(os.environ.get("HOME") or Path.home())
    source_state = source_home / ".arkcli"
    with tempfile.TemporaryDirectory(prefix="ark-cua-arkcli-") as temp_home:
        os.chmod(temp_home, 0o700)
        _copy_arkcli_state(source_state, Path(temp_home) / ".arkcli")
        env = os.environ.copy()
        env["HOME"] = temp_home
        env.setdefault("ARKCLI_CALLER_TYPE", "ai_agent")
        env.setdefault("ARKCLI_CALLER_NAME", "unknown_agent")
        env["ARKCLI_SKILL_NAME"] = ARKCLI_SKILL_NAME
        yield env


def _copy_arkcli_state(source, target):
    """Copy only profile and identity state needed by arkcli read commands."""
    if not source.is_dir():
        return
    target.mkdir(mode=0o700)
    for name in ARKCLI_STATE_FILES:
        source_file = source / name
        if source_file.is_file():
            shutil.copy2(source_file, target / name)
    for name in ARKCLI_STATE_DIRS:
        source_dir = source / name
        if source_dir.is_dir():
            shutil.copytree(source_dir, target / name)


def _arkcli_error_status(stderr, fallback):
    try:
        payload = json.loads(stderr)
    except (TypeError, ValueError):
        return fallback
    error = payload.get("error") if isinstance(payload, dict) else None
    error_type = error.get("type") if isinstance(error, dict) else None
    return error_type if isinstance(error_type, str) and error_type else fallback


def _auth_required(discovery=None, manual=False):
    if manual:
        return SkillError(
            "AUTH_REQUIRED",
            "Manual AgentPlan API key login requires a local hidden prompt.",
            setup_command=login_setup_command(manual=True),
            manual_login_required=True,
        )
    status = (discovery or {}).get("status") or "unavailable"
    hints = {
        "not_installed": "arkcli is not installed; use the local hidden API-key prompt.",
        "no_agent_plan_max_profile": "arkcli has no personal Agent Plan Max profile; log in or open that plan, then retry.",
        "no_api_key": "The arkcli profile has no API key; run `arkcli auth apikey` or `arkcli profile keys refresh`, then retry.",
        "api_key_rejected": "The Agent Plan Max key returned by arkcli was rejected; run `arkcli profile keys refresh` or `arkcli auth apikey`, then retry.",
        "state_snapshot_failed": "arkcli state could not be copied into a private temporary HOME; use the local hidden API-key prompt.",
    }
    return SkillError(
        "AUTH_REQUIRED",
        "AgentPlan API key required for CUA Skill.",
        setup_command=login_setup_command(),
        arkcli_status=status,
        arkcli_hint=hints.get(status, "arkcli could not supply an Agent Plan Max API key; use the local hidden API-key prompt."),
    )


def _auth_error_with_retry(exc, manual=False):
    if _is_agentplan_auth_rejection(exc):
        return SkillError(
            "AUTH_REQUIRED",
            "AgentPlan APIKey 不合法，请输入正确的 APIKey。",
            setup_command=login_setup_command(manual=manual),
            manual_login_required=manual or None,
            auth_type="agentplan_bearer",
        )
    if exc.code in ("AUTH_REQUIRED", "TOKEN_EXPIRED", "REFRESH_FAILED") and "setup_command" not in exc.extra:
        exc.extra["setup_command"] = login_setup_command(manual=manual)
        if manual:
            exc.extra["manual_login_required"] = True
    return exc


def _is_agentplan_auth_rejection(exc):
    if exc.code not in ("AUTH_REQUIRED", "TOKEN_EXPIRED", "FORBIDDEN"):
        return False
    if exc.extra.get("auth_type") == "agentplan_bearer":
        return True
    message = " ".join([
        str(exc.message or ""),
        str(exc.extra.get("reason") or ""),
        str(exc.extra.get("upstream_code") or ""),
    ]).lower()
    if "ark acquire returned status 401" in message or "ark acquire returned status 403" in message:
        return True
    return exc.extra.get("upstream_status") == 401 and (
        "agentplan apikey" in message or "unauthorized" in message
    )


def _scopes(data):
    scopes = data.get("scopes") if isinstance(data, dict) else None
    if isinstance(scopes, list):
        return scopes
    scope = data.get("scope") if isinstance(data, dict) else None
    if isinstance(scope, str):
        return scope.split()
    return []


def _safe_user(user):
    if not isinstance(user, dict):
        return {}
    return {
        "account_id": user.get("account_id") or user.get("accountId"),
        "project_name": user.get("project_name") or user.get("projectName"),
        "apikey_id": user.get("apikey_id") or user.get("api_key_id") or user.get("apiKeyId"),
        "org_id": user.get("org_id"),
        "user_id": user.get("user_id"),
        "email": user.get("email"),
    }
