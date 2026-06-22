#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

"""CLI 公共模块。"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from .vephone_client import VePhoneClient


def _config_candidates(config_path: str) -> list[Path]:
    candidate = Path(config_path)
    if candidate.is_absolute():
        return [candidate]

    candidates = [Path.cwd() / candidate]
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidates.append(parent / candidate)
    return candidates


def load_config(config_path: str = "config.json") -> dict:
    for candidate in _config_candidates(config_path):
        if candidate.exists():
            with candidate.open('r', encoding='utf-8') as f:
                return json.load(f)
    return {}


def config_value(config: dict, key: str, env_key: str, default: Optional[str] = None) -> Optional[str]:
    return config.get(key) or config.get(env_key) or default


def request_kwargs(args) -> dict:
    kwargs = {}
    product_id = getattr(args, 'product_id', None)
    if product_id is not None:
        kwargs['ProductId'] = product_id
    return kwargs


def get_client() -> VePhoneClient:
    access_key = os.getenv('VOLC_ACCESS_KEY')
    secret_key = os.getenv('VOLC_SECRET_KEY')
    region = 'cn-north-1'
    tos_bucket = os.getenv('VOLC_TOS_BUCKET')
    tos_region = os.getenv('VOLC_TOS_REGION')
    tos_endpoint = os.getenv('VOLC_TOS_ENDPOINT')
    tos_prefix = os.getenv('VOLC_TOS_PREFIX')

    if not access_key or not secret_key:
        config = load_config()
        access_key = config_value(config, 'access_key', 'VOLC_ACCESS_KEY')
        secret_key = config_value(config, 'secret_key', 'VOLC_SECRET_KEY')
        tos_bucket = config_value(config, 'tos_bucket', 'VOLC_TOS_BUCKET')
        tos_region = config_value(config, 'tos_region', 'VOLC_TOS_REGION')
        tos_endpoint = config_value(config, 'tos_endpoint', 'VOLC_TOS_ENDPOINT')
        tos_prefix = config_value(config, 'tos_prefix', 'VOLC_TOS_PREFIX')

    if not access_key or not secret_key:
        print("错误: 请设置环境变量 VOLC_ACCESS_KEY 和 VOLC_SECRET_KEY，或配置 config.json 文件")
        sys.exit(1)

    return VePhoneClient(
        access_key,
        secret_key,
        region,
        tos_bucket=tos_bucket,
        tos_region=tos_region,
        tos_endpoint=tos_endpoint,
        tos_prefix=tos_prefix,
    )


def print_result(result: dict, indent: int = 2):
    print(json.dumps(result, indent=indent, ensure_ascii=False))


def parse_string_params(items: Optional[list], option_name: str = '--payload') -> dict:
    params = {}
    for item in items or []:
        if '=' not in item:
            raise SystemExit(f'{option_name} 必须是 Key=value 格式')
        key, value = item.split('=', 1)
        if not key:
            raise SystemExit(f'{option_name} key 不能为空')
        params[key] = value
    return params


def parse_csv_values(value: Optional[str], value_type=str):
    if not value:
        return None
    return [value_type(item) for item in value.split(',') if item != '']


def parse_csv(value: str) -> list:
    return [item for item in value.split(',') if item]


def parse_bool_flag(value: str) -> bool:
    if isinstance(value, bool):
        return value
    lowered = value.lower()
    if lowered in {'true', '1', 'yes', 'y'}:
        return True
    if lowered in {'false', '0', 'no', 'n'}:
        return False
    raise argparse.ArgumentTypeError('布尔值必须是 true/false')


def parse_json_option(value: Optional[str], option_name: str, expected_type: Optional[type] = None) -> Any:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f'{option_name} 必须是合法 JSON: {exc.msg}') from exc
    if expected_type is not None and not isinstance(parsed, expected_type):
        raise SystemExit(f'{option_name} 必须是 {expected_type.__name__} JSON')
    return parsed


def parse_app_list(value: str) -> list[dict]:
    stripped = value.strip()
    if stripped.startswith('['):
        parsed = parse_json_option(value, '--app-list', list)
        for item in parsed:
            if not isinstance(item, dict) or 'AppId' not in item or 'VersionId' not in item:
                raise SystemExit('--app-list JSON 数组中的每项都必须包含 AppId 和 VersionId')
        return parsed

    app_list = []
    for item in value.split(','):
        if not item:
            continue
        if ':' not in item:
            raise SystemExit('--app-list 必须是 AppId:VersionId,AppId2:VersionId2 或 JSON 数组')
        app_id, version_id = item.split(':', 1)
        if not app_id or not version_id:
            raise SystemExit('--app-list 中的 AppId 和 VersionId 不能为空')
        app_list.append({'AppId': app_id, 'VersionId': version_id})
    if not app_list:
        raise SystemExit('--app-list 不能为空')
    return app_list
