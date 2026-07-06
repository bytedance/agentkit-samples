#!/usr/bin/env python3
# Copyright (c) 2026 Beijing Volcano Engine Technology Ltd.
# SPDX-License-Identifier: Apache-2.0

from __future__ import print_function

import argparse
import sys

from modules.scene import register_scene
from modules.model import register_model
from modules.deployment import register_deployment
from modules.apikey import register_apikey
from modules.openapi import register_openapi
from modules.console import register_console


def build_parser() -> argparse.ArgumentParser:
    """构建顶层 CLI 解析器，并委托各模块注册子命令。"""
    parser = argparse.ArgumentParser(
        description=(
            "Volcano Engine ContextSearch CLI：管理 ContextSearch 资源（当前支持 "
            "列举场景 ListScene、查询场景详情 GetScene、按模板检查/部署后创建普通/AgenticSearch 场景 CreateScene/CreateAgenticScene、配置场景存储位置 UpdateScene、"
            "发布场景 CreateSceneVersion、查询场景版本 ListSceneVersion、启动/停止场景 StartSceneInstance/StopSceneInstance、"
            "编辑场景名称 UpdateScene、删除场景 DeleteScene、查询可用规格 GetAIInstanceSpec、数据导入 AddSceneData、查看数据列表 ListSceneData、查看切片列表 ListSceneDataChunk、"
            "列举公共/自定义模型 ListAIModel、"
            "列举预置/自定义推理服务 ListAIDeployment、查询推理服务详情 GetAIDeployment、"
            "查询推理服务用量 GetArkEndpointUsage、查询/创建/删除 API Key ListMLApiKeys/CreateMLApiKey/DeleteMLApiKey，"
            "以及通过 console/openapi 覆盖控制台长尾 action）"
        ),
    )
    ns_parsers = parser.add_subparsers(dest="namespace", required=True)

    # 交由各模块完成命名空间及子命令注册
    register_scene(ns_parsers)
    register_model(ns_parsers)
    register_deployment(ns_parsers)
    register_apikey(ns_parsers)
    register_console(ns_parsers)
    register_openapi(ns_parsers)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    # 每个子命令通过 set_defaults(func=...) 注册处理函数
    args.func(args)


if __name__ == "__main__":
    main()
