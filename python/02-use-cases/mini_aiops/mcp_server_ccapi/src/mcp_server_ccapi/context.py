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

from mcp_server_ccapi.errors import ServerError


class Context:
    """A singleton which includes context for the MCP server such as startup parameters."""

    _instance = None

    def __init__(self, readonly_mode: bool):
        """Initializes the context."""
        self._readonly_mode = readonly_mode

    @classmethod
    def readonly_mode(cls) -> bool:
        """If a the server was started up with the argument --readonly True, this will be set to True."""
        if cls._instance is None:
            raise ServerError('Context was not initialized')
        return cls._instance._readonly_mode

    @classmethod
    def initialize(cls, readonly_mode: bool):
        """Create the singleton instance of the type."""
        cls._instance = cls(readonly_mode)
