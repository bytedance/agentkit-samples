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

"""Infrastructure generation implementation for CCAPI MCP server."""

import datetime
import uuid
from mcp_server_ccapi.errors import ClientError
from mcp.server.fastmcp import Context
from mcp_server_ccapi.impl.utils.validation import (
    validate_workflow_token,
)
from mcp_server_ccapi.infrastructure_generator import (
    generate_infrastructure_code as generate_infrastructure_code_impl,
)
from mcp_server_ccapi.models.models import (
    GenerateInfrastructureCodeRequest,
)


async def generate_infrastructure_code_impl_wrapper(
    ctx: Context,
    request: GenerateInfrastructureCodeRequest, workflow_store: dict
) -> dict:
    """Generate infrastructure code before resource creation or update implementation."""
    # Validate credentials token
    cred_data = validate_workflow_token(request.credentials_token, 'credentials', workflow_store)
    volcengine_session_data = cred_data['data']
    if not volcengine_session_data.get('credentials_valid'):
        raise ClientError('Invalid Volcengine credentials')

    # V1: Always add required MCP server identification tags
    # Inform user about default tags and ask if they want additional ones

    # Generate infrastructure code using the existing implementation
    result = await generate_infrastructure_code_impl(
        ctx=ctx,
        resource_type=request.resource_type,
        properties=request.properties,
        identifier=request.identifier,
        patch_document=request.patch_document,
        region=request.region or volcengine_session_data.get('region') or 'cn-beijing',
    )

    # Generate a generated code token that enforces using the exact properties and template
    generated_code_token = f'generated_code_{str(uuid.uuid4())}'

    # Store structured workflow data including both properties and  template
    workflow_store[generated_code_token] = {
        'type': 'generated_code',
        'data': {
            'properties': result['properties'],
            'cloudcontrol_template': result.get('cloudcontrol_template', result['properties']),
        },
        'parent_token': request.credentials_token,
        'timestamp': datetime.datetime.now().isoformat(),
    }

    # Keep credentials token for later use in create_resource()

    return {
        'generated_code_token': generated_code_token,
        'message': 'Infrastructure code generated successfully. Use generated_code_token with explain()',
        'next_step': 'Use explain() with generated_code_token, then create_resource() with explained_token.',
        **result,  # Include all infrastructure code data for display
    }
