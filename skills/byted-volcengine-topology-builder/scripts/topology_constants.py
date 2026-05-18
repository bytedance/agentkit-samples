#!/usr/bin/env python3

BUSINESS_ROOT_DIR = "business_topologies"
DEFAULT_BUSINESS_KEY = "default-topology"
DEFAULT_ENV_FILE_NAME = ".env"

ASSETS_SNAPSHOT_FILE_NAME = "account_assets_snapshot.json"
TOPOLOGY_JSON_FILE_NAME = "topology.json"
TOPOLOGY_MD_FILE_NAME = "topology.md"
TOPOLOGY_DOT_FILE_NAME = "topology.dot"
TOPOLOGY_SVG_FILE_NAME = "topology.svg"
TOPOLOGY_PNG_FILE_NAME = "topology.png"

DEFAULT_INCLUDE_TYPES = [
    "ecs",
    "eip",
    "clb",
    "alb",
    "natgateway",
    "rds_mysql",
    "redis",
]

DEFAULT_ENTRY_TYPES = ["eip", "clb", "alb", "natgateway"]
