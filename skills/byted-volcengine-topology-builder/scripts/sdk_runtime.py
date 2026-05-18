#!/usr/bin/env python3
import importlib
import inspect
import os
import re
from typing import Any, Dict, Optional

from volcenginesdkcore import ApiClient, Configuration
from volcenginesdkcore.universal import UniversalApi, UniversalInfo

SCRIPT_DIR = os.path.dirname(__file__)
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
DEFAULT_REGION = "cn-shanghai"
DEFAULT_ENV_PATH = os.path.join(os.getcwd(), ".env")


class ScriptError(Exception):
    """脚本统一异常类型。"""


def read_env_file(env_path: str = DEFAULT_ENV_PATH) -> Dict[str, str]:
    env_values: Dict[str, str] = {}
    if not env_path or not os.path.exists(env_path):
        return env_values

    with open(env_path, "r", encoding="utf-8") as file_obj:
        for raw_line in file_obj:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env_values[key.strip()] = value.strip().strip("\"'")
    return env_values


def get_runtime_env(env_path: str = DEFAULT_ENV_PATH) -> Dict[str, str]:
    merged_env = dict(read_env_file(env_path))
    for key, value in os.environ.items():
        if value:
            merged_env[key] = value
    return merged_env


def get_credentials(env_path: str = DEFAULT_ENV_PATH) -> Dict[str, Optional[str]]:
    runtime_env = get_runtime_env(env_path)
    return {
        "ak": runtime_env.get("VOLCENGINE_AK"),
        "sk": runtime_env.get("VOLCENGINE_SK"),
        "region": runtime_env.get("VOLCENGINE_REGION") or DEFAULT_REGION,
        "env_path": env_path,
    }


def ensure_credentials(env_path: str = DEFAULT_ENV_PATH) -> Dict[str, Optional[str]]:
    # 优先读取显式传入的 .env，再由系统环境变量覆盖，确保脚本可独立运行。
    credentials = get_credentials(env_path)
    if not credentials["ak"] or not credentials["sk"]:
        raise ScriptError(
            "缺少认证信息，请设置 VOLCENGINE_AK/VOLCENGINE_SK 或在 .env 文件中配置"
        )
    return credentials


SERVICE_SPECS = {
    "ecs": {"module": "ecs", "api_class": "ECSApi"},
    "eip": {"module": "vpc", "api_class": "VPCApi"},
    "clb": {"module": "clb", "api_class": "CLBApi"},
    "alb": {"module": "alb", "api_class": "ALBApi"},
    "natgateway": {"module": "natgateway", "api_class": "NATGATEWAYApi"},
    "rds_mysql": {"module": "rdsmysql", "api_class": "RDSMYSQLApi"},
    "redis": {"module": "redis", "api_class": "REDISApi"},
}

RAW_ACTION_FALLBACK_SPECS = {
    # RDS MySQL 的部分响应字段枚举比本地 SDK 模型更新更快。
    # 当模型反序列化失败时，回退到原始 OpenAPI JSON，避免资产采集中断。
    ("rds_mysql", "ListDBInstances"): {
        "version": "2018-01-01",
        "method": "POST",
        "content_type": "application/json",
    }
}


def camel_to_snake(name: str) -> str:
    # 同时处理普通驼峰和包含缩写的名字，例如：
    # - DescribeDBInstances -> describe_db_instances
    # - ListDBInstancesRequest -> list_db_instances_request
    step1 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    step2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", step1)
    return step2.lower()


def get_service_spec(service_key: str) -> Dict[str, str]:
    spec = SERVICE_SPECS.get(service_key)
    if spec is None:
        raise ScriptError(f"不支持的服务类型: {service_key}")
    return spec


def build_api(service_key: str, region: str, env_path: str = DEFAULT_ENV_PATH) -> Any:
    credentials = ensure_credentials(env_path)
    resolved_region = region or credentials["region"] or DEFAULT_REGION
    spec = get_service_spec(service_key)

    configuration = Configuration()
    configuration.ak = credentials["ak"]
    configuration.sk = credentials["sk"]
    configuration.region = resolved_region

    module = importlib.import_module(f"volcenginesdk{spec['module']}")
    api_class = getattr(module, spec["api_class"])
    return api_class(ApiClient(configuration))


def build_configuration(region: str, env_path: str = DEFAULT_ENV_PATH) -> Configuration:
    credentials = ensure_credentials(env_path)
    resolved_region = region or credentials["region"] or DEFAULT_REGION

    configuration = Configuration()
    configuration.ak = credentials["ak"]
    configuration.sk = credentials["sk"]
    configuration.region = resolved_region
    return configuration


def build_request(service_key: str, action_name: str, params: Dict[str, Any]) -> Any:
    spec = get_service_spec(service_key)
    request_class_name = f"{action_name}Request"
    request_module_name = camel_to_snake(request_class_name)
    module = importlib.import_module(
        f"volcenginesdk{spec['module']}.models.{request_module_name}"
    )
    request_class = getattr(module, request_class_name)

    # 这里按构造函数签名过滤参数，避免把不属于该接口的字段误传进去。
    signature = inspect.signature(request_class.__init__)
    accepted_params = {
        key: value
        for key, value in params.items()
        if key in signature.parameters and value is not None
    }
    return request_class(**accepted_params)


def normalize_data_keys(value: Any) -> Any:
    if isinstance(value, list):
        return [normalize_data_keys(item) for item in value]
    if isinstance(value, dict):
        return {
            camel_to_snake(str(key)): normalize_data_keys(item)
            for key, item in value.items()
        }
    return value


def call_action_via_raw_openapi(
    service_key: str,
    action_name: str,
    params: Dict[str, Any],
    *,
    region: str,
    env_path: str = DEFAULT_ENV_PATH,
) -> Dict[str, Any]:
    fallback_spec = RAW_ACTION_FALLBACK_SPECS.get((service_key, action_name))
    if fallback_spec is None:
        raise ScriptError(f"{service_key}.{action_name} 不支持原始 OpenAPI 回退")

    configuration = build_configuration(region, env_path)
    api = UniversalApi(ApiClient(configuration))
    response = api.do_call(
        UniversalInfo(
            method=fallback_spec["method"],
            service=service_key,
            version=fallback_spec["version"],
            action=action_name,
            content_type=fallback_spec["content_type"],
        ),
        {key: value for key, value in params.items() if value is not None},
    )
    return normalize_data_keys(to_plain_data(response))


def call_action(
    service_key: str,
    action_name: str,
    params: Dict[str, Any],
    *,
    region: str,
    env_path: str = DEFAULT_ENV_PATH,
) -> Dict[str, Any]:
    api = build_api(service_key, region, env_path)
    method_name = camel_to_snake(action_name)
    if not hasattr(api, method_name):
        raise ScriptError(f"{service_key} 不存在 SDK 方法: {method_name}")

    request_obj = build_request(service_key, action_name, params)
    try:
        response = getattr(api, method_name)(request_obj)
        return to_plain_data(response)
    except ValueError:
        if (service_key, action_name) not in RAW_ACTION_FALLBACK_SPECS:
            raise
        return call_action_via_raw_openapi(
            service_key,
            action_name,
            params,
            region=region,
            env_path=env_path,
        )


def to_plain_data(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [to_plain_data(item) for item in value]
    if isinstance(value, dict):
        return {key: to_plain_data(item) for key, item in value.items()}
    if hasattr(value, "to_dict"):
        return to_plain_data(value.to_dict())
    if hasattr(value, "__dict__"):
        return {
            key: to_plain_data(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return value
