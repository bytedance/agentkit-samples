"""Run AgentKit CLI with an explicit HTTP OIDC compatibility switch.

AgentKit CLI 0.5.5 requires an HTTPS OIDC Discovery URL during local config
validation.  The hybrid-cloud POC user-pool endpoint is currently HTTP-only.
This wrapper changes only that in-process validation rule, and only when the
caller explicitly sets AGENTKIT_ALLOW_HTTP_OIDC=1.  It does not modify the
installed AgentKit package or any Runtime authentication behavior.
"""

from __future__ import annotations

import os
from dataclasses import fields

from agentkit.toolkit.config.constants import AUTH_TYPE_CUSTOM_JWT
from agentkit.toolkit.config.strategy_configs import (
    CloudStrategyConfig,
    HybridStrategyConfig,
)


def _allow_http_oidc_for_poc() -> None:
    if os.environ.get("AGENTKIT_ALLOW_HTTP_OIDC") != "1":
        return

    for config_class in (HybridStrategyConfig, CloudStrategyConfig):
        for config_field in fields(config_class):
            if config_field.name != "runtime_jwt_discovery_url":
                continue
            rule = config_field.metadata["validation"]["rules"][
                AUTH_TYPE_CUSTOM_JWT
            ]
            rule["pattern"] = r"^https?://.+"
            rule["hint"] = "(must be a valid HTTP(S) URL)"
            rule["message"] = "must be a valid HTTP(S) URL"


def main() -> None:
    _allow_http_oidc_for_poc()
    from agentkit.toolkit.cli.cli import app

    app()


if __name__ == "__main__":
    main()
