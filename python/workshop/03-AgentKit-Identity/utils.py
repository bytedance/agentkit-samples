import base64
import hashlib
import hmac
import secrets
import string
from typing import Optional
import requests
import volcenginesdkcore
from volcenginesdkcore.rest import ApiException
import volcenginesdkid
from veadk.integrations.ve_identity import IdentityClient
from veadk.config import settings
import os


def _generate_runtime_password(length: int = 16) -> str:
    """
    生成运行时固定的密码
    包含大小写字母、数字和特殊字符，满足密码强度要求
    """
    # 确保至少包含: 1个大写字母、1个小写字母、1个数字、1个特殊字符
    uppercase = secrets.choice(string.ascii_uppercase)
    lowercase = secrets.choice(string.ascii_lowercase)
    digit = secrets.choice(string.digits)
    special = secrets.choice("!@#$%^&*")

    # 剩余字符随机选择
    remaining_length = length - 4
    all_chars = string.ascii_letters + string.digits + "!@#$%^&*"
    remaining = "".join(secrets.choice(all_chars) for _ in range(remaining_length))

    # 组合并打乱顺序
    password_list = list(uppercase + lowercase + digit + special + remaining)
    secrets.SystemRandom().shuffle(password_list)
    return "".join(password_list)


# 运行时固定的用户密码（模块加载时生成一次，后续复用）
# 用于 create_user 和 reauthenticate_user 保持一致
DEFAULT_USER_PASSWORD = _generate_runtime_password()


def veidentity_initiate_auth(
    client_id,
    auth_flow,
    auth_parameters,
    pool_id,
    custom_domain,
    client_secret=None,
):
    """
    使用 veIdentity Auth Frost API 进行用户认证

    Args:
        client_id: 应用客户端ID
        auth_flow: 认证流程 (USER_PASSWORD_AUTH | REFRESH_TOKEN_AUTH)
        auth_parameters: 认证参数字典
        client_secret: 客户端密钥 (可选)
        custom_domain: 自定义域名 (可选)

    Returns:
        认证结果字典
    """
    # 如果有客户端密钥，计算 SECRET_HASH
    if client_secret:
        if auth_flow == "USER_PASSWORD_AUTH":
            message = auth_parameters["USERNAME"] + client_id
        elif auth_flow == "REFRESH_TOKEN_AUTH":
            message = auth_parameters["REFRESH_TOKEN"] + client_id
        else:
            message = ""

        secret_hash = base64.b64encode(
            hmac.new(client_secret.encode(), message.encode(), hashlib.sha256).digest()
        ).decode()
        auth_parameters["SECRET_HASH"] = secret_hash

    # 构建请求
    url = f"{custom_domain}/userpool/{pool_id}/api/v1/InitiateAuth"

    payload = {
        "AuthFlow": auth_flow,
        "AuthParameters": auth_parameters,
        "ClientId": client_id,
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()

    return response.json()


def setup_veidentity_user_pool(
    *,
    user_pool="UserPool",
    user_pool_client="UserPoolClient",
    preferred_username="testuser",
    region="cn-beijing",
):
    endpoint = settings.veidentity.get_endpoint()
    configuration = volcenginesdkcore.Configuration()
    configuration.region = region
    configuration.ak = os.environ["VOLCENGINE_ACCESS_KEY"]
    configuration.sk = os.environ["VOLCENGINE_SECRET_KEY"]
    # Initialize veIdentity client
    veidentity_client = volcenginesdkid.IDApi(
        volcenginesdkcore.ApiClient(configuration)
    )
    try:
        list_user_pool_response: volcenginesdkid.ListUserPoolsResponse = (
            veidentity_client.list_user_pools(
                volcenginesdkid.ListUserPoolsRequest(
                    filter={"Name": user_pool}, page_number=1, page_size=1
                )
            )
        )

        pool_id: str
        if len(list_user_pool_response.data) == 0:
            # Create User Pool
            user_pool_response: volcenginesdkid.CreateUserPoolResponse = (
                veidentity_client.create_user_pool(
                    volcenginesdkid.CreateUserPoolRequest(name=user_pool)
                )
            )
            pool_id = user_pool_response.uid
        else:
            pool_id = list_user_pool_response.data[0].uid
    except Exception:
        user_pool_response: volcenginesdkid.CreateUserPoolResponse = (
            veidentity_client.create_user_pool(
                volcenginesdkid.CreateUserPoolRequest(name=user_pool)
            )
        )
        pool_id = user_pool_response.uid
    print("User Pool ID: " + pool_id)
    try:
        list_user_pool_client_response: volcenginesdkid.ListUserPoolClientsResponse = (
            veidentity_client.list_user_pool_clients(
                volcenginesdkid.ListUserPoolClientsRequest(
                    filter={"Name": user_pool_client},
                    page_number=1,
                    page_size=1,
                    user_pool_uid=pool_id,
                )
            )
        )

        client_id, client_secret = None, None
        if len(list_user_pool_client_response.data) == 0:
            # Create User Pool
            app_client_response: volcenginesdkid.CreateUserPoolClientResponse = (
                veidentity_client.create_user_pool_client(
                    volcenginesdkid.CreateUserPoolClientRequest(
                        user_pool_uid=pool_id,
                        client_type="WEB_APPLICATION",
                        name=user_pool_client,
                    )
                )
            )
            client_id = app_client_response.uid
            client_secret = app_client_response.client_secret
        else:
            client_id = list_user_pool_client_response.data[0].uid
            app_client_response: volcenginesdkid.GetUserPoolClientResponse = (
                veidentity_client.get_user_pool_client(
                    volcenginesdkid.GetUserPoolClientRequest(
                        user_pool_uid=pool_id,
                        client_uid=client_id,
                    )
                )
            )
            client_secret = app_client_response.client_secret
    except Exception:
        # Create User Pool
        app_client_response: volcenginesdkid.CreateUserPoolClientResponse = (
            veidentity_client.create_user_pool_client(
                volcenginesdkid.CreateUserPoolClientRequest(
                    user_pool_uid=pool_id,
                    client_type="WEB_APPLICATION",
                    name=user_pool_client,
                )
            )
        )
        client_id = app_client_response.uid
        client_secret = app_client_response.client_secret
    print(f"Client ID: {client_id}")
    print(f"Client Secret: {client_secret}")
    user_uid = None
    try:
        list_user_response: volcenginesdkid.ListUsersResponse = (
            veidentity_client.list_users(
                volcenginesdkid.ListUsersRequest(
                    user_pool_uid=pool_id,
                    page_number=1,
                    page_size=1,
                    filter={"PreferredUsername": preferred_username},
                )
            )
        )
        if len(list_user_response.data) == 0:
            # Create User
            res: volcenginesdkid.CreateUserResponse = veidentity_client.create_user(
                volcenginesdkid.CreateUserRequest(
                    user_pool_uid=pool_id,
                    email=f"{preferred_username}@example.com",
                    preferred_username=preferred_username,
                    password=DEFAULT_USER_PASSWORD,
                )
            )
            user_uid = res.uid
        else:
            user_uid = list_user_response.data[0].uid
    except Exception:
        res: volcenginesdkid.CreateUserResponse = veidentity_client.create_user(
            volcenginesdkid.CreateUserRequest(
                user_pool_uid=pool_id,
                email=f"{preferred_username}@example.com",
                preferred_username=preferred_username,
                password=DEFAULT_USER_PASSWORD,
            )
        )
        user_uid = res.uid

    print("User UID: " + user_uid)

    veidentity_client.update_user(
        volcenginesdkid.UpdateUserRequest(
            user_pool_uid=pool_id,
            user_uid=user_uid,
            user_state="CONFIRMED",
        )
    )
    try:
        # Authenticate User and get Access Token
        auth_response = veidentity_initiate_auth(
            client_id=client_id,
            client_secret=client_secret,
            auth_flow="USER_PASSWORD_AUTH",
            auth_parameters={
                "USERNAME": preferred_username,
                "PASSWORD": DEFAULT_USER_PASSWORD,
            },
            pool_id=pool_id,
            custom_domain=f"https://auth.{endpoint}",
        )
        bearer_token = auth_response["Result"]["AuthenticationResult"]["AccessToken"]
        # Output the required values
        print(
            f"Discovery URL: https://auth.{endpoint}/userpool/{pool_id}/.well-known/openid-configuration"
        )
        # print(f"Bearer Token: {bearer_token}")

        # Return values if needed for further processing
        return {
            "pool_id": pool_id,
            "client_id": client_id,
            "client_secret": client_secret,
            "bearer_token": bearer_token,
            "preferred_username": preferred_username,
            "discovery_url": f"https://auth.{endpoint}/userpool/{pool_id}/.well-known/openid-configuration",
        }
    except Exception as e:
        print(f"Error: {e}")
        return None


def reauthenticate_user(
    *,
    client_id: str,
    pool_id: str,
    preferred_username="testuser",
    client_secret: Optional[str] = None,
):
    # Initialize veIdentity client
    auth_response = veidentity_initiate_auth(
        client_id=client_id,
        client_secret=client_secret,
        auth_flow="USER_PASSWORD_AUTH",
        auth_parameters={
            "USERNAME": preferred_username,
            "PASSWORD": DEFAULT_USER_PASSWORD,
        },
        pool_id=pool_id,
        custom_domain=f"https://auth.{settings.veidentity.get_endpoint()}",
    )
    bearer_token = auth_response["Result"]["AuthenticationResult"]["AccessToken"]
    return bearer_token


def create_oauth2_credential_provider(
    product_name: str,
    identity_client: IdentityClient,
    region: str = "cn-beijing",
) -> volcenginesdkid.CreateOauth2CredentialProviderResponse:
    if identity_client is None:
        identity_client = IdentityClient(region=region)
    try:
        return identity_client.create_oauth2_credential_provider_with_dcr(
            {
                "name": f"volc-{product_name}-oauth-provider",
                "vendor": 0,  # Custom Vendor
                "config": {
                    "Scopes": ["read"],
                    "RedirectUrl": f"https://auth.{settings.veidentity.get_endpoint()}/api/v1/oauth2callback",
                    "Oauth2Discovery": {
                        "AuthorizationServerMetadata": {
                            "AuthorizationEndpoint": "https://signin.volcengine.com/authorize/oauth/authorize",
                            "Issuer": "https://signin.volcengine.com",
                            "TokenEndpoint": f"https://{product_name}.mcp.volcbiz.com/auth/oauth/token",
                            "RegisterEndpoint": f"https://{product_name}.mcp.volcbiz.com/auth/oauth/register",
                        }
                    },
                },
            }
        )
    except ApiException as e:
        if "Duplicate entry" in e.reason:
            print("provider already exists")
        else:
            print(e.reason)
