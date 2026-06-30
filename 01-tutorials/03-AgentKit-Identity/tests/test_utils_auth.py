from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
import string
import sys
import types
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "utils.py"


class FakeApiException(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class FakeIdentityClient:
    def __init__(self, region: str = "cn-beijing"):
        self.region = region
        self.requests = []

    def create_oauth2_credential_provider_with_dcr(self, payload):
        self.requests.append(payload)
        return {"created": payload}


class FakeVeIdentitySettings:
    @staticmethod
    def get_endpoint():
        return "identity.example.com"


def install_dependency_stubs():
    volcenginesdkcore = types.ModuleType("volcenginesdkcore")
    volcenginesdkcore.Configuration = type("Configuration", (), {})
    volcenginesdkcore.ApiClient = lambda configuration: ("api_client", configuration)

    rest_module = types.ModuleType("volcenginesdkcore.rest")
    rest_module.ApiException = FakeApiException

    volcenginesdkid = types.ModuleType("volcenginesdkid")
    request_names = [
        "ListUserPoolsRequest",
        "CreateUserPoolRequest",
        "ListUserPoolClientsRequest",
        "CreateUserPoolClientRequest",
        "GetUserPoolClientRequest",
        "ListUsersRequest",
        "CreateUserRequest",
        "UpdateUserRequest",
    ]
    response_names = [
        "ListUserPoolsResponse",
        "CreateUserPoolResponse",
        "ListUserPoolClientsResponse",
        "CreateUserPoolClientResponse",
        "GetUserPoolClientResponse",
        "ListUsersResponse",
        "CreateUserResponse",
        "CreateOauth2CredentialProviderResponse",
    ]
    for name in request_names + response_names:
        setattr(volcenginesdkid, name, type(name, (), {}))
    volcenginesdkid.IDApi = lambda api_client: ("id_api", api_client)

    veadk = types.ModuleType("veadk")
    integrations = types.ModuleType("veadk.integrations")
    ve_identity = types.ModuleType("veadk.integrations.ve_identity")
    ve_identity.IdentityClient = FakeIdentityClient

    config = types.ModuleType("veadk.config")
    config.settings = types.SimpleNamespace(veidentity=FakeVeIdentitySettings())

    sys.modules["volcenginesdkcore"] = volcenginesdkcore
    sys.modules["volcenginesdkcore.rest"] = rest_module
    sys.modules["volcenginesdkid"] = volcenginesdkid
    sys.modules["veadk"] = veadk
    sys.modules["veadk.integrations"] = integrations
    sys.modules["veadk.integrations.ve_identity"] = ve_identity
    sys.modules["veadk.config"] = config


@pytest.fixture()
def identity_utils():
    install_dependency_stubs()
    spec = importlib.util.spec_from_file_location("agentkit_identity_utils", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def expected_secret_hash(secret: str, message: str) -> str:
    digest = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def test_generate_runtime_password_contains_required_character_classes(identity_utils):
    password = identity_utils._generate_runtime_password(24)

    assert len(password) == 24
    assert any(char in string.ascii_uppercase for char in password)
    assert any(char in string.ascii_lowercase for char in password)
    assert any(char in string.digits for char in password)
    assert any(char in "!@#$%^&*" for char in password)
    assert set(password).issubset(set(string.ascii_letters + string.digits + "!@#$%^&*"))


def test_default_user_password_is_generated_once_at_import(identity_utils):
    first = identity_utils.DEFAULT_USER_PASSWORD
    second = identity_utils.DEFAULT_USER_PASSWORD

    assert first == second
    assert len(first) == 16


def test_veidentity_initiate_auth_posts_expected_payload_without_secret(
    identity_utils, monkeypatch
):
    calls = []

    class Response:
        def raise_for_status(self):
            calls.append(("raise_for_status",))

        def json(self):
            return {"Result": {"ok": True}}

    def fake_post(url, json):
        calls.append(("post", url, json))
        return Response()

    monkeypatch.setattr(identity_utils.requests, "post", fake_post)
    auth_parameters = {"USERNAME": "alice", "PASSWORD": "secret"}

    result = identity_utils.veidentity_initiate_auth(
        client_id="client-1",
        auth_flow="USER_PASSWORD_AUTH",
        auth_parameters=auth_parameters,
        pool_id="pool-1",
        custom_domain="https://auth.example.com",
    )

    assert result == {"Result": {"ok": True}}
    assert calls == [
        (
            "post",
            "https://auth.example.com/userpool/pool-1/api/v1/InitiateAuth",
            {
                "AuthFlow": "USER_PASSWORD_AUTH",
                "AuthParameters": {"USERNAME": "alice", "PASSWORD": "secret"},
                "ClientId": "client-1",
            },
        ),
        ("raise_for_status",),
    ]
    assert "SECRET_HASH" not in auth_parameters


@pytest.mark.parametrize(
    ("auth_flow", "auth_parameters", "message"),
    [
        (
            "USER_PASSWORD_AUTH",
            {"USERNAME": "alice", "PASSWORD": "secret"},
            "aliceclient-1",
        ),
        (
            "REFRESH_TOKEN_AUTH",
            {"REFRESH_TOKEN": "refresh-token"},
            "refresh-tokenclient-1",
        ),
        ("CUSTOM_AUTH", {"USERNAME": "alice"}, ""),
    ],
)
def test_veidentity_initiate_auth_adds_secret_hash_for_supported_flows(
    identity_utils, monkeypatch, auth_flow, auth_parameters, message
):
    captured_payload = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": True}

    def fake_post(url, json):
        captured_payload["url"] = url
        captured_payload["json"] = json
        return Response()

    monkeypatch.setattr(identity_utils.requests, "post", fake_post)

    identity_utils.veidentity_initiate_auth(
        client_id="client-1",
        auth_flow=auth_flow,
        auth_parameters=auth_parameters,
        pool_id="pool-1",
        custom_domain="https://auth.example.com",
        client_secret="client-secret",
    )

    assert captured_payload["url"].endswith("/userpool/pool-1/api/v1/InitiateAuth")
    assert captured_payload["json"]["AuthParameters"]["SECRET_HASH"] == (
        expected_secret_hash("client-secret", message)
    )


def test_veidentity_initiate_auth_propagates_http_errors(identity_utils, monkeypatch):
    class Response:
        def raise_for_status(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(identity_utils.requests, "post", lambda url, json: Response())

    with pytest.raises(RuntimeError, match="boom"):
        identity_utils.veidentity_initiate_auth(
            client_id="client-1",
            auth_flow="USER_PASSWORD_AUTH",
            auth_parameters={"USERNAME": "alice", "PASSWORD": "secret"},
            pool_id="pool-1",
            custom_domain="https://auth.example.com",
        )


def test_reauthenticate_user_returns_access_token(identity_utils, monkeypatch):
    captured = {}

    def fake_initiate_auth(**kwargs):
        captured.update(kwargs)
        return {"Result": {"AuthenticationResult": {"AccessToken": "token-123"}}}

    monkeypatch.setattr(identity_utils, "veidentity_initiate_auth", fake_initiate_auth)

    token = identity_utils.reauthenticate_user(
        client_id="client-1",
        pool_id="pool-1",
        preferred_username="alice",
        client_secret="client-secret",
    )

    assert token == "token-123"
    assert captured["client_id"] == "client-1"
    assert captured["client_secret"] == "client-secret"
    assert captured["auth_flow"] == "USER_PASSWORD_AUTH"
    assert captured["auth_parameters"]["USERNAME"] == "alice"
    assert captured["pool_id"] == "pool-1"
    assert captured["custom_domain"] == "https://auth.identity.example.com"


def test_create_oauth2_credential_provider_builds_expected_payload(identity_utils):
    identity_client = FakeIdentityClient()

    result = identity_utils.create_oauth2_credential_provider(
        "weather",
        identity_client,
    )

    payload = identity_client.requests[0]
    assert result == {"created": payload}
    assert payload["name"] == "volc-weather-oauth-provider"
    assert payload["vendor"] == 0
    assert payload["config"]["Scopes"] == ["read"]
    assert payload["config"]["RedirectUrl"] == (
        "https://auth.identity.example.com/api/v1/oauth2callback"
    )
    metadata = payload["config"]["Oauth2Discovery"]["AuthorizationServerMetadata"]
    assert metadata["TokenEndpoint"] == "https://weather.mcp.volcbiz.com/auth/oauth/token"
    assert metadata["RegisterEndpoint"] == (
        "https://weather.mcp.volcbiz.com/auth/oauth/register"
    )


def test_create_oauth2_credential_provider_creates_default_client(identity_utils):
    result = identity_utils.create_oauth2_credential_provider(
        "calendar",
        identity_client=None,
        region="cn-shanghai",
    )

    payload = result["created"]
    assert payload["name"] == "volc-calendar-oauth-provider"
    assert payload["config"]["Oauth2Discovery"]["AuthorizationServerMetadata"][
        "TokenEndpoint"
    ] == "https://calendar.mcp.volcbiz.com/auth/oauth/token"


def test_create_oauth2_credential_provider_swallows_duplicate_error(identity_utils):
    class DuplicateClient:
        def create_oauth2_credential_provider_with_dcr(self, payload):
            raise FakeApiException("Duplicate entry for provider")

    assert (
        identity_utils.create_oauth2_credential_provider(
            "weather",
            DuplicateClient(),
        )
        is None
    )
