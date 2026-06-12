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

"""Security scanning implementation for CCAPI MCP server."""

import datetime
import json
import os
import subprocess
import tempfile
import uuid
from mcp_server_ccapi.errors import ClientError
from mcp_server_ccapi.models.models import RunCheckovRequest


def _check_checkov_installed() -> dict:
    """Check if Checkov is available.

    Since checkov is now a declared dependency, it should always be available.
    This function mainly serves as a validation step.

    Returns:
        A dictionary with status information:
        {
            "installed": True/False,
            "message": Description of what happened,
            "needs_user_action": True/False
        }
    """
    try:
        # Check if Checkov is available
        subprocess.run(
            ['checkov', '--version'],
            capture_output=True,
            text=True,
            check=True,
            shell=False,
        )
        return {
            'installed': True,
            'message': 'Checkov is available',
            'needs_user_action': False,
        }
    except (FileNotFoundError, subprocess.CalledProcessError):
        return {
            'installed': False,
            'message': 'Checkov is not available. This should not happen as checkov is a declared dependency. Please reinstall the package.',
            'needs_user_action': True,
        }


async def run_security_analysis(resource_type: str, properties: dict) -> dict:
    """Simple security analysis function for test compatibility."""
    return {'passed': True, 'message': 'Security analysis passed'}


async def run_checkov_impl(request: RunCheckovRequest, workflow_store: dict) -> dict:
    """Run Checkov security and compliance scanner on server-stored cloudcontrol template implementation."""
    # Check if Checkov is installed
    checkov_status = _check_checkov_installed()
    if not checkov_status['installed']:
        return {
            'passed': False,
            'error': 'Checkov is not installed',
            'summary': {'error': 'Checkov not installed'},
            'message': checkov_status['message'],
            'requires_confirmation': checkov_status['needs_user_action'],
            'options': [
                {
                    'option': 'install_help',
                    'description': 'Get help installing Checkov',
                },
                {
                    'option': 'proceed_without',
                    'description': 'Proceed without security checks',
                },
                {'option': 'cancel', 'description': 'Cancel the operation'},
            ],
        }

    # CRITICAL SECURITY: Validate explained token and get server-stored cloudcontrol template
    if request.explained_token not in workflow_store:
        raise ClientError('Invalid explained token: you must call explain() first')

    workflow_data = workflow_store[request.explained_token]
    if workflow_data.get('type') != 'explained_properties':
        raise ClientError('Invalid token type: expected explained_properties token from explain()')

    # Get cloudcontrol template from server-stored data (AI cannot override this)
    cloudcontrol_template = workflow_data['data']['cloudcontrol_template']
    resource_type = workflow_data['data']['properties'].get('Type', 'Unknown')

    # Ensure content is a string for Checkov
    if not isinstance(cloudcontrol_template, str):
        try:
            content = json.dumps(cloudcontrol_template)
        except Exception as e:
            return {
                'passed': False,
                'error': f'cloudcontrol template must be valid JSON: {str(e)}',
                'summary': {'error': 'Invalid cloudcontrol template format'},
            }
    else:
        content = cloudcontrol_template

    # Create a temporary file with the cloudcontrol template (always JSON)
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
        temp_file.write(content.encode('utf-8'))
        temp_file_path = temp_file.name

    try:
        # Build the checkov command with input validation
        cmd = ['checkov', '-f', temp_file_path, '--output', 'json']

        # Add framework if specified (validate against allowed frameworks)
        if request.framework:
            allowed_frameworks = [
                'terraform',
                'cloudcontrol',
                'kubernetes',
                'dockerfile',
                'arm',
                'all',
            ]
            if request.framework in allowed_frameworks:
                cmd.extend(['--framework', request.framework])
            else:
                return {
                    'passed': False,
                    'error': f'Invalid framework: {request.framework}. Allowed: {allowed_frameworks}',
                }

        # Run checkov with shell=False for security
        process = subprocess.run(cmd, capture_output=True, text=True, shell=False)

        # Parse the output
        if process.returncode == 0:
            # All checks passed - generate security scan token
            security_scan_token = f'sec_{str(uuid.uuid4())}'

            workflow_store[security_scan_token] = {
                'type': 'security_scan',
                'data': {
                    'passed': True,
                    'scan_results': (json.loads(process.stdout) if process.stdout else []),
                    'resource_type': resource_type,
                    'timestamp': str(datetime.datetime.now()),
                },
                'timestamp': datetime.datetime.now().isoformat(),
            }

            return {
                'scan_status': 'PASSED',
                'raw_failed_checks': [],
                'raw_passed_checks': (json.loads(process.stdout) if process.stdout else []),
                'raw_summary': {
                    'passed': True,
                    'message': 'All security checks passed',
                },
                'resource_type': resource_type,
                'timestamp': str(datetime.datetime.now()),
                'security_scan_token': security_scan_token,
                'message': 'Security checks passed. You can proceed with create_resource().',
            }
        elif process.returncode == 1:  # Return code 1 means vulnerabilities were found
            # Some checks failed
            try:
                results = json.loads(process.stdout) if process.stdout else {}
                failed_checks = results.get('results', {}).get('failed_checks', [])
                passed_checks = results.get('results', {}).get('passed_checks', [])
                summary = results.get('summary', {})

                # Security issues found - return results with security_scan_token
                security_scan_token = f'sec_{str(uuid.uuid4())}'

                workflow_store[security_scan_token] = {
                    'type': 'security_scan',
                    'data': {
                        'passed': False,
                        'scan_results': {
                            'failed_checks': failed_checks,
                            'passed_checks': passed_checks,
                            'summary': summary,
                        },
                        'resource_type': resource_type,
                        'timestamp': str(datetime.datetime.now()),
                    },
                    'timestamp': datetime.datetime.now().isoformat(),
                }

                return {
                    'scan_status': 'FAILED',
                    'raw_failed_checks': failed_checks,
                    'raw_passed_checks': passed_checks,
                    'raw_summary': summary,
                    'resource_type': resource_type,
                    'timestamp': str(datetime.datetime.now()),
                    'security_scan_token': security_scan_token,
                    'message': 'Security issues found. You can proceed with create_resource() if you approve.',
                }
            except json.JSONDecodeError:
                # Handle case where output is not valid JSON
                return {
                    'passed': False,
                    'error': 'Failed to parse Checkov output',
                    'stdout': process.stdout,
                    'stderr': process.stderr,
                }
        else:
            # Error running checkov
            return {
                'passed': False,
                'error': f'Checkov exited with code {process.returncode}',
                'stderr': process.stderr,
            }
    except Exception as e:
        return {'passed': False, 'error': str(e), 'message': 'Failed to run Checkov'}
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
