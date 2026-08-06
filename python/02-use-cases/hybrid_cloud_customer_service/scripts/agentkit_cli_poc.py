"""Run AgentKit CLI with narrowly scoped hybrid-cloud compatibility switches.

AgentKit CLI 0.5.5 requires an HTTPS OIDC Discovery URL during local config
validation.  The hybrid-cloud POC user-pool endpoint is currently HTTP-only.
This wrapper changes only that in-process validation rule, and only when the
caller explicitly sets AGENTKIT_ALLOW_HTTP_OIDC=1.  It does not modify the
installed AgentKit package or any Runtime authentication behavior.

When requested by the deployment script, the wrapper also exposes only the
Docker SDK's build/push DEBUG records.  Other AgentKit loggers keep their
normal levels so control-plane request details are not made verbose.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import fields

from agentkit.toolkit.config.constants import AUTH_TYPE_CUSTOM_JWT
from agentkit.toolkit.config.strategy_configs import (
    CloudStrategyConfig,
    HybridStrategyConfig,
)


class _DockerDebugOnly(logging.Filter):
    """Keep the scoped handler from duplicating normal AgentKit log lines."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno == logging.DEBUG


def _enable_verbose_docker_logs() -> logging.Handler | None:
    """Expose Docker SDK build/push progress without enabling global DEBUG."""

    if os.environ.get("AGENTKIT_VERBOSE_DOCKER_LOGS") != "1":
        return None

    docker_logger = logging.getLogger("agentkit.toolkit.docker.container")
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)
    handler.addFilter(_DockerDebugOnly())
    handler.setFormatter(logging.Formatter("[docker] %(message)s"))
    docker_logger.addHandler(handler)
    docker_logger.setLevel(logging.DEBUG)
    return handler


def _allow_http_oidc_for_poc() -> None:
    if os.environ.get("AGENTKIT_ALLOW_HTTP_OIDC") != "1":
        return

    for config_class in (HybridStrategyConfig, CloudStrategyConfig):
        for config_field in fields(config_class):
            if config_field.name != "runtime_jwt_discovery_url":
                continue
            rule = config_field.metadata["validation"]["rules"][AUTH_TYPE_CUSTOM_JWT]
            rule["pattern"] = r"^https?://.+"
            rule["hint"] = "(must be a valid HTTP(S) URL)"
            rule["message"] = "must be a valid HTTP(S) URL"


def main() -> None:
    _allow_http_oidc_for_poc()
    _enable_verbose_docker_logs()
    from agentkit.toolkit.cli.cli import app

    app()


if __name__ == "__main__":
    main()
