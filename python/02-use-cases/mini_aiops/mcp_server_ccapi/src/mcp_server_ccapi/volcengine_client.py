# Copyright (c) Amazon.com, Inc. or its affiliates.
# Copyright (c) 2025 ByteDance Ltd. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
# This file has been modified by ByteDance Ltd. and/or its affiliates on 2025-10-30.
#
# Original file was released under the Apache License, Version 2.0.
# The full license text is available at:
#     http://www.apache.org/licenses/LICENSE-2.0
#
# This modified file is released under the same license.

import json
import os
import asyncio
from typing import Any
from mcp_server_ccapi.impl.tools.credential import (
    get_volcengine_credentials,
)
from volcenginesdkcore import ApiClient, Configuration, UniversalApi, UniversalInfo
from volcenginesdkcore.rest import ApiException
from mcp.server.fastmcp import Context


def create_universal_info(
    service,
    action,
    version='2021-09-01',
    method='POST',
    content_type='application/json',
):
    if content_type is None:
        content_type = 'application/json'
    if method == 'GET':
        content_type = 'text/plain'

    return UniversalInfo(
        method=method,
        service=service,
        version=version,
        action=action,
        content_type=content_type,
    )


def get_volcengine_client_from_config(ctx: Context, region: str | None):
    """Create and return a Volcengine service client from configuration.

    Args:
        ctx (Context): Volcengine configuration context.
        region: Volcengine region name (defaults to 'cn-beijing')

    Returns:
        volcenginesdkcore UniversalApi client
    """
    credentials = get_volcengine_credentials(ctx, region)
    return get_volcengine_client(
        ak=credentials['access_key_id'],
        sk=credentials['secret_access_key'],
        session_token=credentials['session_token'],
        region=region or credentials['region'],
        host=credentials['host'],
    )


def get_volcengine_client(
    ak,
    sk,
    session_token='',
    region='cn-beijing',
    host='cloudcontrol.cn-beijing.volcengineapi.com',
    scheme='https',
):
    """Create and return a Volcengine service client.

    Args:
        ak: Volcengine access key
        sk: Volcengine secret key
        session_token: Volcengine session token (optional)
        region: Volcengine region name (defaults to boto3's default region resolution)
        host: Volcengine host (defaults to 'open.volcengineapi.com')
        scheme: Volcengine scheme (defaults to 'https')

    Returns:
        volcenginesdkcore UniversalApi client
    """
    config = Configuration()
    config.ak = ak
    config.sk = sk
    config.host = host  # pyright: ignore[reportAttributeAccessIssue]
    config.scheme = scheme
    config.region = region
    if session_token:
        config.session_token = session_token
    api_client = ApiClient(config)
    from mcp_server_ccapi import __version__

    api_client.user_agent = 'mcp-server-ccapi/' + __version__
    return UniversalApi(api_client)


_CONCURRENCY = int(os.getenv('MCP_SERVER_CONCURRENCY', '16') or '16')
_api_semaphore: asyncio.Semaphore | None = None

def _get_semaphore() -> asyncio.Semaphore:
    global _api_semaphore
    if _api_semaphore is None:
        _api_semaphore = asyncio.Semaphore(_CONCURRENCY)
    return _api_semaphore

async def do_call_with_http_info_async(
    client: UniversalApi,
    info: UniversalInfo,
    body: dict | None
) -> Any:
    async with _get_semaphore():
        return await asyncio.to_thread(
            client.do_call_with_http_info,
            info=info,
            body=body
        )

# 使用示例
if __name__ == '__main__':
    # 创建API客户端

    volcengine_client = get_volcengine_client(
        ak='....',
        sk='.....==',
        session_token='',
        host='cloudcontrol.cn-beijing.volcengineapi.com',
    )
    # 创建UniversalInfo
    info = create_universal_info(
        service='cloudcontrol',
        action='DescribeResourceType',
        version='2025-06-01',
        method='GET',
        content_type='application/json',
    )
    params = {'TypeName': 'Volcengine::IAM::User'}
    try:
        resp, status_code, resp_header = volcengine_client.do_call_with_http_info(  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType, reportGeneralTypeIssues]
            info=info, body=params
        )
    except ApiException as ae:
        # 解析错误响应
        if not hasattr(ae, 'body'):
            raise ae
        try:
            body_dict = json.loads(ae.body)  # pyright: ignore[reportUnknownMemberType, reportArgumentType]
            # 检查是否需要添加处理建议
            if (
                'ResponseMetadata' in body_dict
                and 'Error' in body_dict['ResponseMetadata']
                and 'Message' in body_dict['ResponseMetadata']['Error']
            ):
                msg = body_dict['ResponseMetadata']['Error']['Message']
                if 'cannot be modified during update' in msg and 'createOnlyProperty' in msg:
                    body_dict['Error']['Suggestion'] = (
                        'If an error occurs indicating that the property cannot be modified (e.g., "createOnlyProperty xxx cannot be modified during update"), call `list_resource_types()` to find a suitable resource type that allows modification. Once a suitable resource type is found, proceed with the necessary modifications using the alternative resource type.'
                    )
            # 重新抛出带有建议的异常
            ae.body = json.dumps(body_dict)
            raise ae
        except Exception:
            raise ae
    except Exception as e:
        print(f'Error: {e}')
        raise e
    print(f'Status Code: {status_code}')
    print(f'Response: {resp}')
    print(resp['Schema'])
    spec = json.dumps(resp['Schema'], ensure_ascii=False)
    print(spec)
