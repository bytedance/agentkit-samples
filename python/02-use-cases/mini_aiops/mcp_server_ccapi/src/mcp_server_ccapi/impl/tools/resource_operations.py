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

"""Resource operations implementation for CCAPI MCP server."""

import json
from mcp_server_ccapi.cloud_control_utils import (
    progress_event,
    validate_patch,
)
from mcp.server.fastmcp import Context
from mcp_server_ccapi.context import Context as ServerContext
from mcp_server_ccapi.errors import (
    ClientError,
    handle_volcengine_api_error,
)
from mcp_server_ccapi.impl.utils.validation import (
    cleanup_workflow_tokens,
    ensure_region_string,
    validate_identifier,
    validate_resource_type,
    validate_workflow_token,
)
from mcp_server_ccapi.models.models import (
    CreateResourceRequest,
    DeleteResourceRequest,
    GetResourceRequest,
    UpdateResourceRequest,
)
from mcp_server_ccapi.volcengine_client import (
    create_universal_info,
    get_volcengine_client_from_config,
    do_call_with_http_info_async
)
from os import environ
from volcenginesdkcore.rest import ApiException


def check_readonly_mode(volcengine_session_data: dict) -> None:
    """Check if server is in read-only mode and raise error if so."""
    if ServerContext.readonly_mode() or volcengine_session_data.get('readonly_mode', False):
        raise ClientError('Server is in read-only mode')


def check_security_scanning() -> tuple[bool, str | None]:
    """Check if security scanning is enabled and return warning if disabled."""
    security_scanning_enabled = environ.get('SECURITY_SCANNING', 'disabled').lower() == 'enabled'
    security_warning = None

    if not security_scanning_enabled:
        security_warning = '⚠️ SECURITY SCANNING IS DISABLED. This MCP server is configured with SECURITY_SCANNING=disabled, which means resources will be created/updated WITHOUT automated security validation. For security best practices, consider enabling SECURITY_SCANNING in your MCP configuration or ensure other security scanning tools are in place.'

    return security_scanning_enabled, security_warning


def _validate_token_chain(
    explained_token: str, security_scan_token: str, workflow_store: dict
) -> None:
    """Validate that tokens are from the same workflow chain."""
    if not explained_token or explained_token not in workflow_store:
        raise ClientError('Invalid explained_token')

    if not security_scan_token or security_scan_token not in workflow_store:
        raise ClientError('Invalid security_scan_token')

    # Security scan token must be created after explain token in same workflow
    explained_data = workflow_store[explained_token]
    security_data = workflow_store[security_scan_token]

    # For now, just ensure both tokens exist and are valid types
    if explained_data.get('type') != 'explained_properties':
        raise ClientError('Invalid explained_token type')

    if security_data.get('type') != 'security_scan':
        raise ClientError('Invalid security_scan_token type')

    # Set the parent relationship (security scan derives from explained token)
    workflow_store[security_scan_token]['parent_token'] = explained_token


async def create_resource_impl(ctx:Context, request: CreateResourceRequest, workflow_store: dict) -> dict:
    """Create an Volcengine resource implementation."""
    validate_resource_type(request.resource_type)

    # Check if security scanning is enabled
    security_scanning_enabled, security_warning = check_security_scanning()

    # Validate security scan token if security scanning is enabled
    if security_scanning_enabled:
        if not request.security_scan_token:
            raise ClientError(
                'Security scanning is enabled but no security_scan_token provided: run run_checkov() first and get user approval via approve_security_findings()'
            )

        # Validate token chain
        _validate_token_chain(request.explained_token, request.security_scan_token, workflow_store)
    elif not security_scanning_enabled and not request.skip_security_check:
        raise ClientError(
            'Security scanning is disabled. You must set skip_security_check=True to proceed without security validation.'
        )

    # Validate credentials token
    cred_data = validate_workflow_token(request.credentials_token, 'credentials', workflow_store)
    volcengine_session_data = cred_data['data']
    if not volcengine_session_data.get('credentials_valid'):
        raise ClientError('Invalid Volcengine credentials')

    # Read-only mode check
    check_readonly_mode(volcengine_session_data)

    # CRITICAL SECURITY: Get properties from validated explained token only
    workflow_data = validate_workflow_token(
        request.explained_token, 'explained_properties', workflow_store
    )

    # Use ONLY the properties that were explained - no manual override possible
    properties = workflow_data['data']['properties']

    # Ensure region is a string, not a FieldInfo object
    region_str = ensure_region_string(request.region)
    cloudcontrol_client = get_volcengine_client_from_config(ctx, region_str)
    try:
        universal_info = create_universal_info(
            method='POST',
            service='cloudcontrol',
            version='2025-06-01',
            action='CreateResource',
            content_type='application/json',
        )
        param = {'TypeName': request.resource_type, 'TargetState': properties}
        response, _, _ = await do_call_with_http_info_async(
            cloudcontrol_client,
            universal_info,
            param,
        )
    except ApiException as ae:
        error_message = getattr(ae, 'body', None)
        try:
            error_body = json.loads(error_message) if error_message else {}
            error_code = error_body.get('ResponseMetadata').get('Error').get('Code')
            if error_code == 'EntityNotFound':
                raise ClientError(
                    'invalid resource type, you can use list_resource_types() to get all resource types.'
                )
            raise handle_volcengine_api_error(ae)
        except Exception as iee:
            raise handle_volcengine_api_error(iee)
    except Exception as e:
        raise handle_volcengine_api_error(e)

    # Clean up consumed tokens after successful operation
    cleanup_workflow_tokens(
        workflow_store,
        request.explained_token,
        request.security_scan_token or '',
    )

    result = progress_event(response, None)
    return result


async def update_resource_impl(ctx: Context, request: UpdateResourceRequest, workflow_store: dict) -> dict:
    """Update a Volcengine resource implementation."""
    validate_resource_type(request.resource_type)
    validate_identifier(request.identifier)

    if not request.patch_document:
        raise ClientError('Please provide a patch document for the update')

    # Validate credentials token
    cred_data = validate_workflow_token(request.credentials_token, 'credentials', workflow_store)
    volcengine_session_data = cred_data['data']
    if not volcengine_session_data.get('credentials_valid'):
        raise ClientError('Invalid Volcengine credentials')

    # Check read-only mode
    try:
        check_readonly_mode(volcengine_session_data)
    except ClientError:
        raise ClientError(
            'You have configured this tool in readonly mode. To make this change you will have to update your configuration.'
        )

    # Check if security scanning is enabled
    security_scanning_enabled, security_warning = check_security_scanning()

    # Validate security scan token if security scanning is enabled
    if security_scanning_enabled and not request.security_scan_token:
        raise ClientError('Security scan token required (run run_checkov() first)')

    # CRITICAL SECURITY: Validate explained token (already validated in token chain if security enabled)
    if not security_scanning_enabled or request.skip_security_check:
        validate_workflow_token(request.explained_token, 'explained_properties', workflow_store)
    else:
        # Token already validated in chain
        pass

    validate_patch(request.patch_document)
    # Ensure region is a string, not a FieldInfo object
    region_str = ensure_region_string(request.region)
    cloudcontrol_client = get_volcengine_client_from_config(ctx, region_str)
    response = None
    # Update the resource
    try:
        universal_info = create_universal_info(
            service='cloudcontrol',
            action='UpdateResource',
            version='2025-06-01',
            method='POST',
            content_type='application/json',
        )
        params = {
            'TypeName': request.resource_type,
            'Identifier': request.identifier,
            'PatchDocument': request.patch_document,
        }
        response, _, _ = await do_call_with_http_info_async(
            cloudcontrol_client,
            universal_info,
            params,
        )
    except ApiException as ae:
        # 解析错误响应
        if not hasattr(ae, 'body'):
            raise ae
        try:
            body_dict = json.loads(ae.body)
            # 检查是否需要添加处理建议
            if (
                'ResponseMetadata' in body_dict
                and 'Error' in body_dict['ResponseMetadata']
                and 'Message' in body_dict['ResponseMetadata']['Error']
            ):
                msg = body_dict['ResponseMetadata']['Error']['Message']
                if 'cannot be modified during update' in msg and 'createOnlyProperty' in msg:
                    body_dict['ResponseMetadata']['Error']['Suggestion'] = (
                        'If an error occurs indicating that the property cannot be modified (e.g., "createOnlyProperty xxx cannot be modified during update"), call `list_resource_types()` to identify alternative resource types, select one that supports the desired modification, and retry the update using that resource type.'
                    )
            # 重新抛出带有建议的异常
            ae.body = json.dumps(body_dict)
            raise handle_volcengine_api_error(ae)
        except Exception:
            raise handle_volcengine_api_error(ae)
    except Exception as e:
        raise handle_volcengine_api_error(e)

    # Clean up consumed tokens after successful operation
    cleanup_workflow_tokens(
        workflow_store,
        request.explained_token,
        request.security_scan_token or '',
    )

    result = progress_event(response, None)
    return result


async def delete_resource_impl(ctx: Context, request: DeleteResourceRequest, workflow_store: dict) -> dict:
    """Delete an Volcengine resource implementation."""
    validate_resource_type(request.resource_type)
    validate_identifier(request.identifier)

    if not request.confirmed:
        raise ClientError(
            'Please confirm the deletion by setting confirmed=True to proceed with resource deletion.'
        )

    # CRITICAL SECURITY: Validate explained token to ensure deletion was explained
    workflow_data = validate_workflow_token(
        request.explained_token, 'explained_delete', workflow_store
    )

    if workflow_data.get('operation') != 'delete':
        raise ClientError('Invalid explained token: token was not generated for delete operation')

    # Validate credentials token
    cred_data = validate_workflow_token(request.credentials_token, 'credentials', workflow_store)
    volcengine_session_data = cred_data['data']
    if not volcengine_session_data.get('credentials_valid'):
        raise ClientError('Invalid Volcengine credentials')

    # Check read-only mode
    try:
        check_readonly_mode(volcengine_session_data)
    except ClientError:
        raise ClientError(
            'You have configured this tool in readonly mode. To make this change you will have to update your configuration.'
        )

    cloudcontrol_client = get_volcengine_client_from_config(ctx, request.region)
    try:
        universal_info = create_universal_info(
            service='cloudcontrol',
            action='DeleteResource',
            version='2025-06-01',
            method='POST',
            content_type='application/json',
        )
        params = {
            'TypeName': request.resource_type,
            'Identifier': request.identifier,
        }
        response, _, _ = await do_call_with_http_info_async(
            cloudcontrol_client,
            universal_info,
            params,
        )
    except Exception as e:
        raise handle_volcengine_api_error(e)

    # Clean up consumed tokens after successful operation
    cleanup_workflow_tokens(workflow_store, request.explained_token)

    return progress_event(response, None)


async def get_resource_impl(
    ctx: Context,
    request: GetResourceRequest,
    workflow_store: dict | None = None
) -> dict:
    """Get details of a specific Volcengine resource implementation."""
    validate_resource_type(request.resource_type)
    validate_identifier(request.identifier)

    cloudcontrol = get_volcengine_client_from_config(ctx, request.region)
    try:
        info = create_universal_info(
            service='cloudcontrol',
            action='GetResource',
            version='2025-06-01',
            method='POST',
            content_type='application/json',
        )
        params = {'TypeName': request.resource_type, 'Identifier': request.identifier}
        result, _, _ = await do_call_with_http_info_async(
            cloudcontrol,
            info,
            params,
        )
        properties_str = result['ResourceDescription']['Properties']  # pyright: ignore[reportCallIssue, reportArgumentType]
        properties = (
            json.loads(properties_str) if isinstance(properties_str, str) else properties_str
        )

        resource_info = {
            'identifier': result['ResourceDescription']['Identifier'],
            'properties': properties,
        }

        # Add security analysis if requested
        if request.analyze_security and workflow_store is not None:
            # Import here to avoid circular imports
            from mcp_server_ccapi.impl.tools.explanation import (
                explain_impl,
            )
            from mcp_server_ccapi.impl.tools.security_scanning import (
                run_checkov_impl,
            )
            from mcp_server_ccapi.impl.tools.session_management import (
                check_environment_variables_impl,
                get_volcengine_session_info_impl,
            )

            env_token = None
            creds_token = None
            gen_token = None
            explained_token = None
            security_scan_token = None
            try:
                # Get credentials token first
                env_check = await check_environment_variables_impl(ctx, workflow_store)
                env_token = env_check['environment_token']
                session_info = await get_volcengine_session_info_impl(ctx, env_token, workflow_store)
                creds_token = session_info['credentials_token']

                # Use existing security analysis workflow
                from mcp_server_ccapi.impl.tools.infrastructure_generation import (
                    generate_infrastructure_code_impl_wrapper,
                )
                from mcp_server_ccapi.models.models import (
                    GenerateInfrastructureCodeRequest,
                )

                gen_request = GenerateInfrastructureCodeRequest(
                    resource_type=request.resource_type,
                    properties=properties or {},
                    credentials_token=creds_token or '',
                    region=request.region,
                )
                generated_code = await generate_infrastructure_code_impl_wrapper(
                    ctx, gen_request, workflow_store
                )
                gen_token = generated_code['generated_code_token']

                from mcp_server_ccapi.models.models import ExplainRequest

                explain_request = ExplainRequest(
                    generated_code_token=gen_token or '', content=None
                )
                explained = await explain_impl(explain_request, workflow_store)
                explained_token = explained['explained_token']

                from mcp_server_ccapi.models.models import (
                    RunCheckovRequest,
                )

                checkov_request = RunCheckovRequest(explained_token=explained_token)
                security_scan = await run_checkov_impl(checkov_request, workflow_store)
                security_scan_token = security_scan.get('security_scan_token')
                resource_info['security_analysis'] = security_scan
            except Exception as e:
                resource_info['security_analysis'] = {
                    'error': f'Security analysis failed: {str(e)}'
                }
            finally:
                # Clean up security analysis tokens that aren't auto-consumed
                # gen_token is consumed by explain(), so only clean remaining tokens
                if workflow_store is not None:
                    cleanup_workflow_tokens(
                        workflow_store,
                        env_token or '',
                        creds_token or '',
                        explained_token or '',
                        security_scan_token or '',
                    )

        return resource_info
    except Exception as e:
        raise handle_volcengine_api_error(e)


async def get_resource_request_status_impl(ctx: Context, request_token: str, region: str | None = None) -> dict:
    """Get the status of a long running operation implementation."""
    if not request_token:
        raise ClientError('Please provide a request token to track the request')

    cloudcontrol_client = get_volcengine_client_from_config(ctx, region)
    try:
        info = create_universal_info(
            service='cloudcontrol',
            action='GetTask',
            version='2025-06-01',
            method='POST',
            content_type='application/json',
        )
        params = {'TaskID': request_token}
        response, _, _ = await do_call_with_http_info_async(
            cloudcontrol_client,
            info,
            params,
        )
    except Exception as e:
        raise handle_volcengine_api_error(e)

    return progress_event(response, None)
