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

"""Infrastructure code generation utilities for the Volcengine MCP Server."""

import json
from mcp_server_ccapi.cloud_control_utils import add_default_tags
from mcp_server_ccapi.errors import (
    ClientError,
    handle_volcengine_api_error,
)
from mcp_server_ccapi.schema_manager import schema_manager
from mcp.server.fastmcp import Context
from mcp_server_ccapi.volcengine_client import (
    create_universal_info,
    get_volcengine_client_from_config,
    do_call_with_http_info_async
)
from typing import List


async def generate_infrastructure_code(
    ctx: Context,
    resource_type: str,
    properties: dict = {},  # pyright: ignore[reportMissingTypeArgument]
    identifier: str = '',
    patch_document: List = [],  # pyright: ignore[reportMissingTypeArgument]
    region: str = '',
) -> dict:  # pyright: ignore[reportMissingTypeArgument]
    """Generate infrastructure code for security scanning before resource creation or update."""
    if not resource_type:
        raise ClientError('Please provide a resource type (e.g., Volcengine::IAM::User)')

    # Determine if this is a create or update operation
    is_update = identifier != '' and (patch_document or properties)

    # Validate the resource type against the schema
    sm = schema_manager()
    schema = await sm.get_schema(ctx, resource_type, region)

    # Check if resource supports tagging
    supports_tagging = 'Tags' in schema.get('properties', {})

    if is_update:
        # This is an update operation
        if not identifier:
            raise ClientError('Please provide a resource identifier for update operations')

        # Get the current resource state
        cloudcontrol_client = get_volcengine_client_from_config(ctx, region)
        try:
            # 创建UniversalInfo
            universal_info = create_universal_info(
                service='cloudcontrol',
                action='GetResource',
                version='2025-06-01',
                method='POST',
                content_type='application/json',
            )
            params = {
                'TypeName': resource_type,
                'Identifier': identifier,
            }
            current_resource, _, _ = await do_call_with_http_info_async(
                cloudcontrol_client,
                universal_info,
                params,
            )
            current_properties = json.loads(current_resource['ResourceDescription']['Properties'])
        except Exception as e:
            raise handle_volcengine_api_error(e)

        # Apply patch document or merge properties
        if patch_document:
            # Apply patch operations to current properties
            import copy

            update_properties = copy.deepcopy(current_properties)
            for patch_op in patch_document:
                if patch_op['op'] == 'add' and patch_op['path'] in ['/Tags', '/Tags/-']:
                    # For Tags, merge with existing tags instead of replacing
                    existing_tags = update_properties.get('Tags', [])
                    if patch_op['path'] == '/Tags/-':
                        # Append single tag to array
                        new_tag = patch_op['value']
                        if isinstance(new_tag, dict) and 'Key' in new_tag and 'Value' in new_tag:
                            existing_tags.append(new_tag)
                            update_properties['Tags'] = existing_tags
                    else:
                        # Replace/merge entire tags array
                        new_tags = patch_op['value'] if isinstance(patch_op['value'], list) else []
                        # Combine tags (new tags will override existing ones with same key)
                        tag_dict = {tag['Key']: tag['Value'] for tag in existing_tags}
                        for tag in new_tags:
                            tag_dict[tag['Key']] = tag['Value']
                        update_properties['Tags'] = [
                            {'Key': k, 'Value': v} for k, v in tag_dict.items()
                        ]
                elif patch_op['op'] == 'replace' and patch_op['path'] == '/Tags':
                    # Replace tags completely
                    update_properties['Tags'] = patch_op['value']
                # Add other patch operations as needed
        elif properties:
            # Start with current properties and merge user properties
            update_properties = current_properties.copy()
            for key, value in properties.items():
                if key == 'Tags':
                    # Merge tags instead of replacing
                    existing_tags = update_properties.get('Tags', [])
                    new_tags = value if isinstance(value, list) else []
                    tag_dict = {tag['Key']: tag['Value'] for tag in existing_tags}
                    for tag in new_tags:
                        tag_dict[tag['Key']] = tag['Value']
                    update_properties['Tags'] = [
                        {'Key': k, 'Value': v} for k, v in tag_dict.items()
                    ]
                else:
                    update_properties[key] = value
        else:
            update_properties = current_properties

        # V1: Always add required MCP server identification tags for updates too
        if supports_tagging:
            properties_with_tags = add_default_tags(properties, schema)
        else:
            properties_with_tags = properties

        operation = 'update'
    else:
        # This is a create operation
        if not properties:
            raise ClientError('Please provide the properties for the desired resource')

        # V1: Always add required MCP server identification tags
        # Check if resource supports tagging
        if supports_tagging:
            properties_with_tags = add_default_tags(properties, schema)
        else:
            properties_with_tags = properties

        operation = 'create'

    # For updates, also generate the proper patch document with default tags
    patch_document_with_tags = None
    if is_update and 'Tags' in properties_with_tags:
        patch_document_with_tags = [
            {'op': 'replace', 'path': '/Tags', 'value': properties_with_tags['Tags']}
        ]

    result = {
        'resource_type': resource_type,
        'operation': operation,
        'properties': properties_with_tags,  # Show user exactly what will be created
        'region': region,
        'supports_tagging': supports_tagging,
    }

    if patch_document_with_tags:
        result['recommended_patch_document'] = patch_document_with_tags  # pyright: ignore[reportArgumentType]

    return result
