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

"""Session management implementation for CCAPI MCP server."""

import datetime
import json
import uuid

from mcp.server.fastmcp import Context
from mcp_server_ccapi.context import Context as ServerContext
from mcp_server_ccapi.errors import ClientError
from mcp_server_ccapi.impl.tools.credential import (
    VOLCENGINE_ACCESS_KEY_ENV,
    VOLCENGINE_SECRET_KEY_ENV,
    VOLCENGINE_SESSION_TOKEN_ENV,
)
from mcp_server_ccapi.schema_manager import get_volcengine_credentials
from mcp_server_ccapi.volcengine_client import (
    create_universal_info,
    get_volcengine_client,
    do_call_with_http_info_async
)
from os import environ
from volcenginesdkcore.rest import ApiException


async def check_environment_variables_impl(ctx: Context, workflow_store: dict) -> dict:
    """Check if required environment variables are set correctly implementation."""
    credentials = get_volcengine_credentials(ctx, None)
    if not (credentials.get("access_key_id") and credentials.get("secret_access_key")):
        raise ClientError('Please provide VOLCENGINE_ACCESS_KEY and VOLCENGINE_SECRET_KEY')

    # Generate environment token
    environment_token = f'env_{str(uuid.uuid4())}'

    # Store environment validation results
    workflow_store[environment_token] = {
        'type': 'environment',
        'data': {
            'environment_variables': {
                'SECURITY_SCANNING': environ.get('SECURITY_SCANNING', 'disable'),
            },
            'ak': credentials.get("access_key_id"),
            'sk': credentials.get('secret_access_key'),
            'session_token': credentials.get('session_token'),
            'properly_configured': True,
        },
        'parent_token': None,  # Root token
        'timestamp': datetime.datetime.now().isoformat(),
    }

    env_data = workflow_store[environment_token]['data']
    # 对 ak/sk 进行中间脱敏
    if 'ak' in env_data and env_data['ak']:
        ak = env_data['ak']
        env_data['ak'] = (
            f'{ak[:4]}{"*" * (len(ak) - 8)}{ak[-4:]}' if len(ak) > 8 else f'{"*" * len(ak)}'
        )
    if 'sk' in env_data and env_data['sk']:
        sk = env_data['sk']
        env_data['sk'] = (
            f'{sk[:4]}{"*" * (len(sk) - 8)}{sk[-4:]}' if len(sk) > 8 else f'{"*" * len(sk)}'
        )
    return {
        'environment_token': environment_token,
        'message': 'Environment validation completed. Use this token with get_volcengine_session_info().',
        **env_data,  # Include environment data for display
    }


async def get_volcengine_session_info_impl(ctx: Context, environment_token: str, workflow_store: dict) -> dict:
    """Get information about the current Volcengine session implementation.

    IMPORTANT: Always display the Volcengine context information to the user when this tool is called.
    Show them: Volcengine Profile (or "Environment Variables"), Authentication Type, Account ID, and Region so they know
    exactly which Volcengine account and region will be affected by any operations.
    """
    credentials = get_volcengine_credentials(ctx, None)
    # Validate environment token
    if environment_token not in workflow_store:
        raise ClientError(
            'Invalid environment token: you must call check_environment_variables() first'
        )

    env_data = workflow_store[environment_token]['data']
    if not env_data.get('properly_configured', False):
        error_msg = env_data.get('error', 'Environment is not properly configured.')
        raise ClientError(error_msg)

    # Get Volcengine profile info using credential checking
    cred_check = await get_volcengine_profile_info(ctx, None)

    if not cred_check.get('valid', False):
        raise ClientError(
            f'Volcengine credentials are not valid: {cred_check.get("error", "Unknown error")}'
        )

    # Generate credentials token
    credentials_token = f'creds_{str(uuid.uuid4())}'

    # Build session info with credential masking
    user_id = str(cred_check.get('user_id', 'Unknown'))
    session_data = {
        'account_id': cred_check.get('account_id', 'Unknown'),
        'user_id': (
            f'{"*" * (len(user_id) - 4)}{user_id[-4:]}'
            if len(user_id) > 4 and user_id != 'Unknown'
            else user_id
        ),
        'readonly_mode': ServerContext.readonly_mode(),
        'readonly_message': (
            """⚠️ This server is running in READ-ONLY MODE. I can only list and view existing resources.
    I cannot create, update, or delete any Volcengine resources. I can still generate example code
    and run security checks on templates."""
            if ServerContext.readonly_mode()
            else ''
        ),
        'credentials_valid': True,
        'volcengine_auth_type': 'env',
    }

    # Add masked environment variables if using env vars
    if session_data['volcengine_auth_type'] == 'env':
        access_key = credentials['access_key_id']
        secret_key = credentials['secret_access_key']
        session_token = credentials['session_token']

        session_data['masked_credentials'] = {
            VOLCENGINE_ACCESS_KEY_ENV: (
                f'{"*" * (len(access_key) - 4)}{access_key[-4:]}'
                if len(access_key) > 4
                else '****'
            ),
            VOLCENGINE_SECRET_KEY_ENV: (
                f'{"*" * (len(secret_key) - 4)}{secret_key[-4:]}'
                if len(secret_key) > 4
                else '****'
            ),
            VOLCENGINE_SESSION_TOKEN_ENV: (
                f'{"*" * (len(session_token) - 4)}{session_token[-4:]}'
                if len(session_token) > 4
                else '****'
            ),
        }

    # Store session information
    workflow_store[credentials_token] = {
        'type': 'credentials',
        'data': session_data,
        'parent_token': environment_token,
        'timestamp': datetime.datetime.now().isoformat(),
    }

    return {
        'credentials_token': credentials_token,
        'message': 'Volcengine session validated. Use this token with generate_infrastructure_code().',
        'DISPLAY_TO_USER': 'YOU MUST SHOW THE USER THEIR VOLCENGINE SESSION INFORMATION FOR SECURITY',
        **session_data,  # Include all session data for display
    }


async def get_volcengine_profile_info(ctx: Context, region: str | None = None):
    """Get information about the current Volcengine"""
    global client
    credentials = get_volcengine_credentials(ctx, region)
    try:
        # Use our get_volcengine_client function to ensure we use the same credential source
        client = get_volcengine_client(
            ak=credentials['access_key_id'],
            sk=credentials['secret_access_key'],
            session_token=credentials['session_token'],
            region=credentials['region'],
            host='open.volcengineapi.com',
        )
        # 创建UniversalInfo
        info = create_universal_info(
            service='iam',
            action='GetUser',
            version='2018-01-01',
            method='GET',
            content_type='application/json',
        )
        params = {'AccessKeyID': credentials['access_key_id']}
        resp, _, _ = await do_call_with_http_info_async(
            client,
            info,
            params,
        )
        return {
            'account_id': resp['User']['AccountId'],
            'account_name': resp['User']['UserName'],
            'Description': resp['User']['Description'],
            'region': credentials['region'] or 'cn-beijing',
            'user_id': resp['User']['Id'],
            'valid': True,
        }
    except ApiException as apie:
        error_message = getattr(apie, 'body', None)
        # 判断 error_message 是否为字符串
        try:
            error_body = json.loads(error_message) if error_message else {}
            error_code = error_body.get('ResponseMetadata').get('Error').get('Code')
            if error_code == 'AccessKeyNotExist':
                # 调用 ListUsers 接口，Limit=1 Offset=1
                info = create_universal_info(
                    service='sts',
                    action='GetCallerIdentity',
                    version='2018-01-01',
                    method='POST',
                    content_type='application/json',
                )
                resp, _, _ = await do_call_with_http_info_async(
                    client,
                    info,
                    {},
                )
                return {
                    'account_id': resp.get('AccountId', 'Unknown'),
                    'account_name': resp.get('AccountId', 'Unknown'),
                    'Description': resp.get('Trn', ''),
                    'region': credentials['region'] or 'cn-beijing',
                    'user_id': resp.get('IdentityId', 'Unknown'),
                    'valid': True,
                }
        except Exception as ie:
            return {
                'valid': False,
                'error': str(ie),
                'region': credentials['region'] or 'cn-beijing',
                'using_env_vars': credentials['access_key_id'] != '' and credentials['secret_access_key'] != '',
            }
    except Exception as e:
        return {
            'valid': False,
            'error': str(e),
            'region': credentials['region'] or 'cn-beijing',
            'using_env_vars': credentials['access_key_id'] != '' and credentials['secret_access_key'] != '',
        }
    return {}
