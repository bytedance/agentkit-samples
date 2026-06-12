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


def handle_volcengine_api_error(e: Exception) -> Exception:
    """Handle Volcengine API errors
    Args:
        e: The exception that was raised

    Returns:
        Standardized ClientError with Volcengine error details
    """
    # Fallback for other exceptions
    return ClientError(f'An error occurred: {str(e)}')


class ClientError(Exception):
    """An error that indicates that the request was malformed or incorrect in some way. There was no issue on the server side."""

    def __init__(self, message):
        """Call super and set message."""
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
        self.type = 'client'
        self.message = message


class ServerError(Exception):
    """An error that indicates that there was an issue processing the request."""

    def __init__(self, message: str):
        """Initialize ServerError with message."""
        super().__init__(message)
        self.type = 'server'
        self.message = message
