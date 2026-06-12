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

"""Pydantic models for CCAPI MCP server requests and responses."""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional


class CreateResourceRequest(BaseModel):
    """Request model for creating VOLCENGINE resources."""

    resource_type: str = Field(..., description='VOLCENGINE resource type')
    region: Optional[str] = Field(None, description='VOLCENGINE region')
    credentials_token: str = Field(..., description='Credentials token')
    explained_token: str = Field(..., description='Explained token')
    security_scan_token: str = Field(default='', description='Security scan token')
    skip_security_check: bool = Field(False, description='Skip security checks')


class UpdateResourceRequest(BaseModel):
    """Request model for updating VOLCENGINE resources."""

    resource_type: str = Field(..., description='VOLCENGINE resource type')
    identifier: str = Field(..., description='Resource identifier')
    patch_document: List[Dict[str, Any]] = Field(default=[], description='JSON Patch operations')
    region: Optional[str] = Field(None, description='VOLCENGINE region')
    credentials_token: str = Field(..., description='Credentials token')
    explained_token: str = Field(..., description='Explained token')
    security_scan_token: str = Field(default='', description='Security scan token')
    skip_security_check: bool = Field(False, description='Skip security checks')


class DeleteResourceRequest(BaseModel):
    """Request model for deleting VOLCENGINE resources."""

    resource_type: str = Field(..., description='VOLCENGINE resource type')
    identifier: str = Field(..., description='Resource identifier')
    region: Optional[str] = Field(None, description='VOLCENGINE region')
    credentials_token: str = Field(..., description='Credentials token')
    confirmed: bool = Field(False, description='Confirm deletion')
    explained_token: str = Field(..., description='Explained token')


class GetResourceRequest(BaseModel):
    """Request model for getting VOLCENGINE resource details."""

    resource_type: str = Field(..., description='VOLCENGINE resource type')
    identifier: str = Field(..., description='Resource identifier')
    region: Optional[str] = Field(None, description='VOLCENGINE region')
    analyze_security: bool = Field(False, description='Perform security analysis')


class GenerateInfrastructureCodeRequest(BaseModel):
    """Request model for generating infrastructure code."""

    resource_type: str = Field(..., description='VOLCENGINE resource type')
    properties: Dict[str, Any] = Field(default_factory=dict, description='Resource properties')
    identifier: str = Field(default='', description='Resource identifier for updates')
    patch_document: List[Dict[str, Any]] = Field(
        default_factory=list, description='JSON Patch operations'
    )
    region: Optional[str] = Field(None, description='VOLCENGINE region')
    credentials_token: str = Field(..., description='Credentials token')


class ExplainRequest(BaseModel):
    """Request model for explaining resource configurations."""

    content: Optional[Any] = Field(None, description='Content to explain')
    generated_code_token: str = Field(default='', description='Generated code token')
    context: str = Field(default='', description='Context description')
    operation: str = Field(default='analyze', description='Operation type')
    format: str = Field(default='detailed', description='Explanation format')
    user_intent: str = Field(default='', description='User intent')


class RunCheckovRequest(BaseModel):
    """Request model for running Checkov security scans."""

    explained_token: str = Field(..., description='Explained token')
    framework: str = Field(default='volcengine', description='Framework to scan')


class ResourceOperationResult(BaseModel):
    """Result model for VOLCENGINE resource operations."""

    status: Literal['SUCCESS', 'PENDING', 'FAILED']
    resource_type: str
    identifier: str
    is_complete: bool
    status_message: str
    request_token: Optional[str] = None
    security_warning: Optional[str] = None


class SecurityScanResult(BaseModel):
    """Result model for security scan operations."""

    scan_status: Literal['PASSED', 'FAILED']
    raw_failed_checks: List[Dict[str, Any]] = Field(default_factory=list)
    raw_passed_checks: List[Dict[str, Any]] = Field(default_factory=list)
    raw_summary: Dict[str, Any] = Field(default_factory=dict)
    resource_type: str
    timestamp: str
    security_scan_token: Optional[str] = None
    message: str
