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

"""Shared validation functions for CCAPI MCP server."""

from mcp_server_ccapi.errors import ClientError


def validate_workflow_token(
    token: str, expected_type: str | None = None, workflow_store: dict | None = None
) -> dict:
    """Validate any workflow token exists and optionally check its type."""
    if not token:
        raise ClientError(f'Invalid token: {token}')
    if not workflow_store:
        raise ClientError('Workflow store is required')
    if token not in workflow_store:
        raise ClientError(f'Invalid token: {token}')

    data = workflow_store[token]
    if expected_type and data.get('type') != expected_type:
        raise ClientError(f'Invalid token type: expected {expected_type}')

    return data


def cleanup_workflow_tokens(workflow_store: dict, *tokens: str) -> None:
    """Clean up workflow tokens after operations."""
    for token in tokens:
        if token and token in workflow_store:
            del workflow_store[token]


def validate_resource_type(resource_type: str) -> None:
    """Validate that resource_type is provided."""
    if not resource_type:
        raise ClientError(
            'Please provide a resource type (e.g., Volcengine::IAM::User), you can use list_resource_types() to get all resource types. '
        )


def validate_identifier(identifier: str) -> None:
    """Validate that identifier is provided."""
    if not identifier:
        raise ClientError('Please provide a resource identifier')


def ensure_region_string(region) -> str | None:
    """Ensure region is a string, not a FieldInfo object."""
    return region if isinstance(region, str) else None


def ensure_string(value, default: str = '') -> str:
    """Ensure value is a string, not a FieldInfo object."""
    return value if isinstance(value, str) else default
