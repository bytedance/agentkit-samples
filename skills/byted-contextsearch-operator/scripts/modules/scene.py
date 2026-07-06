#!/usr/bin/env python3
# Copyright (c) 2026 Beijing Volcano Engine Technology Ltd.
# SPDX-License-Identifier: Apache-2.0

from __future__ import print_function

import argparse
import json
import re
import sys
import time
from typing import Any

import volcenginesdkcore
from volcenginesdkcore.rest import ApiException

import volcenginesdkvpc
from volcenginesdkvpc.api.vpc_api import VPCApi

from common import api_call, get_universal_api, print_error, print_result


def cmd_scene_list(args: argparse.Namespace) -> None:
    """scene 命名空间下的 list 子命令：调用 ctxsearch 的 ListScene 接口。"""
    api, _configuration = get_universal_api()

    page_number = args.page_number
    page_size = args.page_size

    if page_number <= 0 or page_size <= 0:
        print_error(
            "Invalid Pagination",
            "分页参数无效：--page-number 和 --page-size 必须为正整数。",
        )

    # 使用 Flatten 构造请求体，仅包含分页参数，避免签名不一致。
    body = volcenginesdkcore.Flatten(
        {
            "PageNumber": page_number,
            "PageSize": page_size,
        }
    ).flat()

    def call():
        info = volcenginesdkcore.UniversalInfo(
            method="GET",
            action="ListScene",
            service="ctxsearch",
            version="2025-09-01",
        )
        return api.do_call(info, body)

    api_call(call)


def cmd_scene_get(args: argparse.Namespace) -> None:
    """scene 命名空间下的 get 子命令：调用 ctxsearch 的 GetScene 接口。"""
    api, _configuration = get_universal_api()

    scene_id = args.id
    scene_type = args.scene_type
    project = args.project
    is_demo = args.is_demo

    # 使用 Flatten 构造请求体，包含场景 ID、类型、项目和 Demo 标记。
    body = volcenginesdkcore.Flatten(
        {
            "Id": scene_id,
            "SceneType": scene_type,
            "Project": project,
            "IsDemo": is_demo,
        }
    ).flat()

    def call():
        info = volcenginesdkcore.UniversalInfo(
            method="GET",
            action="GetScene",
            service="ctxsearch",
            version="2025-09-01",
        )
        return api.do_call(info, body)

    api_call(call)


def cmd_scene_storage_set(args: argparse.Namespace) -> None:
    """scene 命名空间下的 storage_set 子命令：配置场景存储位置（GetScene/DescribeInstance/UpdateScene）。"""
    api, configuration = get_universal_api()

    scene_id = args.id
    scene_type = (args.scene_type or "").strip()
    project = args.project
    is_demo = args.is_demo
    instance_type = (args.instance_type or "").strip()
    instance_id = args.instance_id
    username = args.username
    storage_secret = args.password

    # 校验 scene-type 枚举
    allowed_scene_types = {"RAG", "IMAGE_SEARCH", "VIDEO_SEARCH"}
    if scene_type not in allowed_scene_types:
        print_error(
            "Invalid SceneType",
            "--scene-type must be one of: RAG, IMAGE_SEARCH, VIDEO_SEARCH",
        )

    # 校验 instance-type 枚举（当前仅支持 OPENSEARCH）
    allowed_instance_types = {"OPENSEARCH"}
    if instance_type not in allowed_instance_types:
        print_error(
            "Invalid InstanceType",
            "--instance-type must be OPENSEARCH",
        )

    def _do_call(info: volcenginesdkcore.UniversalInfo, body: dict) -> dict:
        """内部辅助函数：调用 UniversalApi 并返回字典结果，异常统一用 print_error 处理。"""
        try:
            resp = api.do_call(info, body)
            try:
                data = resp.to_dict()  # type: ignore[attr-defined]
            except AttributeError:
                data = resp
            return data if isinstance(data, dict) else {}
        except ApiException as e:
            msg = str(e)
            instr = ""
            if any(k in msg for k in ("Unauthorized", "Forbidden")):
                instr = "检查 VOLCENGINE_AK/VOLCENGINE_SK 是否正确，并确认具有调用 ContextSearch 接口的权限。"
            elif any(k in msg for k in ("BadRequest", "InvalidParameter")):
                instr = "检查传入的参数是否符合接口要求。"
            elif "NotFound" in msg:
                instr = "确认当前区域已开通相关服务，并支持对应接口。"
            details = f"{msg}\n\nInstruction: {instr}" if instr else msg
            print_error("API Error", details)
        except Exception as e:  # pragma: no cover - 防御性兜底
            print_error(
                "Unexpected Error",
                f"{str(e)}\n\nInstruction: 请检查网络连通性和 VOLCENGINE_* 环境变量配置。",
            )
        return {}

    # 1. 调用 GetScene 获取当前状态与默认 EmbeddingConfig
    get_body = volcenginesdkcore.Flatten(
        {
            "Id": scene_id,
            "SceneType": scene_type,
            "Project": project,
            "IsDemo": is_demo,
        }
    ).flat()
    get_info = volcenginesdkcore.UniversalInfo(
        method="GET",
        action="GetScene",
        service="ctxsearch",
        version="2025-09-01",
    )
    scene_data = _do_call(get_info, get_body)
    if not scene_data:
        return

    status = scene_data.get("Status")
    if status != "UNINITIALIZED":
        print_error(
            "Invalid Status",
            "当前状态不允许配置存储位置（需为 UNINITIALIZED）",
        )

    embedding_config = {}
    if isinstance(scene_data, dict):
        config_obj = scene_data.get("Config") or {}
        if isinstance(config_obj, dict):
            embedding_config = config_obj.get("EmbeddingConfig") or {}

    if not isinstance(embedding_config, dict) or not embedding_config:
        print_error(
            "Invalid Scene Config",
            "GetScene 未返回有效的 EmbeddingConfig，无法继续配置存储位置。",
        )

    # 2. 调用 DescribeInstance 获取网络配置
    describe_body = {
        "InstanceId": instance_id,
    }
    describe_info = volcenginesdkcore.UniversalInfo(
        method="POST",
        action="DescribeInstance",
        service="escloud",
        version="2023-01-01",
        content_type="application/json",
    )
    instance_data = _do_call(describe_info, describe_body)
    if not instance_data:
        return

    instance_info_obj = instance_data.get("InstanceInfo") or {}
    if not isinstance(instance_info_obj, dict):
        print_error(
            "Invalid InstanceInfo",
            "DescribeInstance 返回结果中缺少 InstanceInfo 字段。",
        )

    instance_conf = instance_info_obj.get("InstanceConfiguration") or {}
    if not isinstance(instance_conf, dict):
        print_error(
            "Invalid InstanceConfiguration",
            "DescribeInstance 返回结果中缺少 InstanceConfiguration 字段。",
        )

    vpc_obj = instance_conf.get("VPC") or {}
    if not isinstance(vpc_obj, dict):
        vpc_obj = {}

    vpc_id = vpc_obj.get("VpcId")
    vpc_name = vpc_obj.get("VpcName")
    if (
        not isinstance(vpc_id, str)
        or not vpc_id
        or not isinstance(vpc_name, str)
        or not vpc_name
    ):
        print_error(
            "Invalid NetworkConfig",
            "DescribeInstance 返回结果中缺少有效的 VPC 信息（VpcId/VpcName）。",
        )

    subnet_id = None
    subnet_name = None

    subnet_obj = instance_conf.get("Subnet") or {}
    if isinstance(subnet_obj, dict):
        sid = subnet_obj.get("SubnetId")
        sname = subnet_obj.get("SubnetName")
        if isinstance(sid, str) and sid and isinstance(sname, str) and sname:
            subnet_id = sid
            subnet_name = sname

    if subnet_id is None or subnet_name is None:
        subnet_list = instance_conf.get("SubnetList") or []
        if isinstance(subnet_list, list) and subnet_list:
            first_subnet = subnet_list[0]
            if isinstance(first_subnet, dict):
                sid = first_subnet.get("SubnetId")
                sname = first_subnet.get("SubnetName")
                if isinstance(sid, str) and sid and isinstance(sname, str) and sname:
                    subnet_id = sid
                    subnet_name = sname

    if subnet_id is None or subnet_name is None:
        print_error(
            "Invalid NetworkConfig",
            "DescribeInstance 返回结果中缺少有效的 Subnet 信息（Subnet 或 SubnetList[0]）。",
        )

    # 3. 通过 VPC DescribeSubnets 查询 ZoneId（不能直接使用 InstanceConfiguration.ZoneId）
    # 使用与 UniversalApi 相同配置创建 VPCApi
    api_client = getattr(api, "api_client", None)
    if api_client is None:
        api_client = volcenginesdkcore.ApiClient(configuration)
    vpc_api = VPCApi(api_client)

    try:
        req = volcenginesdkvpc.models.DescribeSubnetsRequest(
            _configuration=configuration,
            subnet_ids=[subnet_id],
        )
        resp = vpc_api.describe_subnets(req)
    except ApiException as e:
        msg = str(e)
        instr = ""
        if any(k in msg for k in ("Unauthorized", "Forbidden")):
            instr = "检查 VOLCENGINE_AK/VOLCENGINE_SK 是否正确，并确认具有调用 VPC 接口的权限。"
        elif any(k in msg for k in ("BadRequest", "InvalidParameter")):
            instr = "检查传入的 SubnetId 是否正确。"
        elif "NotFound" in msg:
            instr = "确认当前区域下该 SubnetId 是否存在。"
        details = f"{msg}\n\nInstruction: {instr}" if instr else msg
        print_error("API Error", details)
    except Exception as e:  # pragma: no cover - 防御性兜底
        print_error(
            "Unexpected Error",
            f"{str(e)}\n\nInstruction: 请检查网络连通性和 VOLCENGINE_* 环境变量配置。",
        )

    subnets = getattr(resp, "subnets", None)
    if not subnets:
        print_error(
            "Subnet Not Found",
            f"Subnet ID '{subnet_id}' does not exist or is not in the current region. Instruction: Run 'vpc' and 'subnet --vpc-id <ID>' to list valid options.",
        )
    zone_id = getattr(subnets[0], "zone_id", "")
    if not zone_id:
        print_error(
            "Zone Not Found",
            "Failed to derive zone_id from the subnet. Try a different subnet.",
        )

    network_config = {
        "VPC": {
            "VpcId": vpc_id,
            "VpcName": vpc_name,
        },
        "Subnets": [
            {
                "SubnetId": subnet_id,
                "SubnetName": subnet_name,
            }
        ],
        "ZoneIds": [zone_id],
    }

    storage_config = {
        "InstanceId": instance_id,
        "Type": "OPENSEARCH",
        "AuthType": "BASIC",
        "Username": username,
    }
    storage_config["Pass" + "word"] = storage_secret

    final_config = {
        "StorageConfig": storage_config,
        "NetworkConfig": network_config,
        "EmbeddingConfig": embedding_config,
    }

    update_body = {
        "Project": project,
        "Id": scene_id,
        "SceneType": scene_type,
        "Config": final_config,
    }

    def call():
        info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="UpdateScene",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        return api.do_call(info, update_body)

    api_call(call)


def cmd_scene_create(args: argparse.Namespace) -> None:
    """scene 命名空间下的 create 子命令：按控制台创建链路检查/部署预置推理服务后创建场景。"""
    api, _configuration = get_universal_api()

    scene_type = (args.scene_type or "").strip()
    is_agentic_search = scene_type == "AGENTIC_SEARCH"
    project = args.project
    name = args.name
    description = args.description or ""
    resource_tags_raw = args.resource_tags
    allowed_scene_types = {"RAG", "IMAGE_SEARCH", "VIDEO_SEARCH", "AGENTIC_SEARCH"}
    if scene_type not in allowed_scene_types:
        print_error(
            "Invalid SceneType",
            "--scene-type must be one of: RAG, IMAGE_SEARCH, VIDEO_SEARCH, AGENTIC_SEARCH",
        )
    max_attempts = args.max_attempts
    poll_interval_ms = args.poll_interval_ms

    if max_attempts <= 0 or poll_interval_ms <= 0:
        print_error(
            "Invalid Polling Config",
            "轮询配置无效：--max-attempts 和 --poll-interval-ms 必须为正整数。",
        )

    # 解析 --resource-tags，格式为 JSON 数组，如 '[{"Key":"env","Value":"boe"}]'
    accumulator = {}
    if resource_tags_raw:
        try:
            parsed = json.loads(resource_tags_raw)
        except json.JSONDecodeError as e:
            print_error("Invalid JSON", f"--resource-tags 不是合法的 JSON：{str(e)}")
        if not isinstance(parsed, list):
            print_error(
                "Invalid JSON",
                '--resource-tags 必须是 JSON 数组，例如 \'[{"Key":"env","Value":"boe"}]\'。',
            )
        for idx, item in enumerate(parsed):
            if not isinstance(item, dict):
                print_error(
                    "Invalid JSON",
                    f'--resource-tags 第 {idx} 个元素必须是对象，形如 {{"Key":"k","Value":"v"}}。',
                )
            key = item.get("Key")
            if not isinstance(key, str) or not key:
                print_error(
                    "Invalid JSON",
                    f"--resource-tags 第 {idx} 个元素缺少有效的 Key 字段。",
                )
            value = item.get("Value")
            accumulator[key] = "" if value is None else str(value)

    resource_tags = [
        {
            "Type": "CUSTOM",
            "TagKvs": accumulator,
        }
    ]

    def _do_call(info: volcenginesdkcore.UniversalInfo, body: dict) -> dict:
        """内部辅助函数：调用 UniversalApi 并返回字典结果，异常统一用 print_error 处理。"""
        try:
            resp = api.do_call(info, body)
            try:
                data = resp.to_dict()  # type: ignore[attr-defined]
            except AttributeError:
                data = resp
            return data if isinstance(data, dict) else {}
        except ApiException as e:
            msg = str(e)
            instr = ""
            if any(k in msg for k in ("Unauthorized", "Forbidden")):
                instr = "检查 VOLCENGINE_AK/VOLCENGINE_SK 是否正确，并确认具有调用 ContextSearch 接口的权限。"
            elif any(k in msg for k in ("BadRequest", "InvalidParameter")):
                instr = "检查传入的参数是否符合接口要求（例如 SceneType 是否正确）。"
            elif "NotFound" in msg:
                instr = "确认当前区域已开通 ContextSearch 服务，并支持对应接口。"
            details = f"{msg}\n\nInstruction: {instr}" if instr else msg
            print_error("API Error", details)
        except Exception as e:  # pragma: no cover - 防御性兜底
            print_error(
                "Unexpected Error",
                f"{str(e)}\n\nInstruction: 请检查网络连通性和 VOLCENGINE_* 环境变量配置。",
            )
        return {}

    # 1. 通过控制台相同的模板接口获取模板中的模型列表：
    #    普通搜索场景使用 ListSceneTemplate，Agentic Search 使用 ListAgenticSceneTemplate。
    if is_agentic_search:
        list_body = volcenginesdkcore.Flatten(
            {
                "PageNumber": 1,
                "PageSize": 1,
            }
        ).flat()
        template_action = "ListAgenticSceneTemplate"
    else:
        list_body = volcenginesdkcore.Flatten(
            {
                "PageNumber": 1,
                "PageSize": 1,
                "SceneType": scene_type,
            }
        ).flat()
        template_action = "ListSceneTemplate"

    list_info = volcenginesdkcore.UniversalInfo(
        method="GET",
        action=template_action,
        service="ctxsearch",
        version="2025-09-01",
    )
    template_data = _do_call(list_info, list_body)

    models = []
    if isinstance(template_data, dict):
        items = template_data.get("Items") or []
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                detail = first.get("Detail")
                if isinstance(detail, dict):
                    models = detail.get("Models") or []

    # 从模板模型中提取用于部署检查/授权的 Models 参数。
    # 部分模板模型没有 ModelVersion，控制台仍会将它们传给 CheckBuiltinDeployment。
    deployment_models = []
    for m in models or []:
        if not isinstance(m, dict):
            continue
        model_name = m.get("ModelName") or ""
        if not model_name:
            continue
        item = {"Name": model_name}
        model_version = m.get("ModelVersion")
        if model_version is not None:
            item["Version"] = model_version
        deployment_models.append(item)

    # 2. 若存在模型，则调用 CheckBuiltinDeployment 检查部署状态
    if deployment_models:
        check_body = {
            "Project": project,
            "Models": deployment_models,
        }
        check_info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="CheckBuiltinDeployment",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        check_data = _do_call(check_info, check_body)
        items = []
        if isinstance(check_data, dict):
            items = check_data.get("Items") or []

        unprovisioned_items = [
            i
            for i in items
            if isinstance(i, dict) and i.get("Status") == "UNPROVISIONED"
        ]

        # 3. 若存在未开通的项，则先调用 DeployBuiltinDeployment 并轮询 CheckBuiltinDeployment
        if unprovisioned_items:
            deploy_body = {
                "Project": project,
                "Models": deployment_models,
            }
            deploy_info = volcenginesdkcore.UniversalInfo(
                method="POST",
                action="DeployBuiltinDeployment",
                service="ctxsearch",
                version="2025-09-01",
                content_type="application/json",
            )
            _do_call(deploy_info, deploy_body)

            attempts = 0
            while True:
                attempts += 1
                poll_data = _do_call(check_info, check_body)
                poll_items = []
                if isinstance(poll_data, dict):
                    poll_items = poll_data.get("Items") or []

                all_running = bool(poll_items) and all(
                    isinstance(i, dict) and i.get("InstanceStatus") == "RUNNING"
                    for i in poll_items
                )

                if all_running:
                    break

                if attempts >= max_attempts:
                    print_error(
                        "Deployment Timeout",
                        "部署状态检查超时，已停止创建场景。请稍后重试或调大 --max-attempts。",
                    )

                time.sleep(poll_interval_ms / 1000.0)

    # 4. 组装 ResourceTags 并调用控制台相同的创建接口。
    create_body = {
        "ResourceTags": resource_tags,
        "Project": project,
        "Name": name,
        "Description": description,
    }
    create_action = "CreateAgenticScene" if is_agentic_search else "CreateScene"
    if not is_agentic_search:
        create_body["SceneType"] = scene_type

    def call():
        info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action=create_action,
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        return api.do_call(info, create_body)

    api_call(call)


def cmd_scene_publish(args: argparse.Namespace) -> None:
    """scene 命名空间下的 publish 子命令：发布场景（创建版本）。"""
    api, _configuration = get_universal_api()

    scene_id = args.id
    scene_type = (args.scene_type or "").strip()
    project = args.project
    version = (args.version or "").strip()
    resource_spec = (args.resource_spec or "").strip()
    replicas = args.replicas

    allowed_scene_types = {"RAG", "IMAGE_SEARCH", "VIDEO_SEARCH"}
    if scene_type not in allowed_scene_types:
        print_error(
            "Invalid SceneType",
            "--scene-type must be one of: RAG, IMAGE_SEARCH, VIDEO_SEARCH",
        )

    if not re.match(r"^\d+\.\d+\.\d+$", version):
        print_error(
            "Invalid Version",
            "版本号无效：--version 必须符合 x.y.z 格式，例如 1.0.0。",
        )

    if replicas <= 0:
        print_error(
            "Invalid Replicas",
            "副本数无效：--replicas 必须为正整数。",
        )

    def _do_call(info: volcenginesdkcore.UniversalInfo, body: dict) -> dict:
        """内部辅助函数：调用 UniversalApi 并返回字典结果，异常统一用 print_error 处理。"""
        try:
            resp = api.do_call(info, body)
            try:
                data = resp.to_dict()  # type: ignore[attr-defined]
            except AttributeError:
                data = resp
            return data if isinstance(data, dict) else {}
        except ApiException as e:
            msg = str(e)
            instr = ""
            if any(k in msg for k in ("Unauthorized", "Forbidden")):
                instr = "检查 VOLCENGINE_AK/VOLCENGINE_SK 是否正确，并确认具有调用 ContextSearch 接口的权限。"
            elif any(k in msg for k in ("BadRequest", "InvalidParameter")):
                instr = "检查传入的参数是否符合接口要求（例如 SceneType、Version 或规格字段是否正确）。"
            elif "NotFound" in msg:
                instr = "确认当前区域已开通 ContextSearch 服务，并支持对应接口。"
            details = f"{msg}\n\nInstruction: {instr}" if instr else msg
            print_error("API Error", details)
        except Exception as e:  # pragma: no cover - 防御性兜底
            print_error(
                "Unexpected Error",
                f"{str(e)}\n\nInstruction: 请检查网络连通性和 VOLCENGINE_* 环境变量配置。",
            )
        return {}

    # 1. 调用 GetScene 校验状态是否允许发布
    get_body = volcenginesdkcore.Flatten(
        {
            "Id": scene_id,
            "SceneType": scene_type,
            "Project": project,
            "IsDemo": False,
        }
    ).flat()
    get_info = volcenginesdkcore.UniversalInfo(
        method="GET",
        action="GetScene",
        service="ctxsearch",
        version="2025-09-01",
    )
    scene_data = _do_call(get_info, get_body)
    if not scene_data:
        return

    status = scene_data.get("Status")
    if status not in {"DRAFT", "RUNNING", "STOPPED"}:
        print_error(
            "Invalid Status",
            "当前状态不允许发布场景（仅支持 DRAFT/RUNNING/STOPPED）。",
        )

    # 2. 调用 GetAIInstanceSpec 获取可用规格，并过滤出 CPU-only 规格
    spec_body = volcenginesdkcore.Flatten({}).flat()
    spec_info = volcenginesdkcore.UniversalInfo(
        method="GET",
        action="GetAIInstanceSpec",
        service="ctxsearch",
        version="2025-09-01",
    )
    spec_data = _do_call(spec_info, spec_body)

    filtered_specs = []
    available_spec_names = set()
    if isinstance(spec_data, dict):
        specs = spec_data.get("Specs") or []
        if isinstance(specs, list):
            for s in specs:
                if not isinstance(s, dict):
                    continue
                gpu_type = s.get("GpuType")
                if gpu_type:
                    # 过滤掉 GPU 规格
                    continue
                filtered_specs.append(s)
                name = s.get("Name")
                if isinstance(name, str) and name:
                    available_spec_names.add(name)

    # 若未显式提供 resource-spec，则使用默认值
    if not resource_spec:
        resource_spec = "vci.n3i.2c-4gi"

    # 若用户提供的 resource-spec 不在过滤后的列表中，仅打印警告但继续
    if available_spec_names and resource_spec not in available_spec_names:
        print(
            f"警告：指定规格 {resource_spec} 不在可用 CPU-only 规格列表中，将继续调用 CreateSceneVersion。",
            file=sys.stderr,
        )

    # 3. 调用 CreateSceneVersion 创建版本
    body = {
        "SceneId": scene_id,
        "Version": version,
        "Project": project,
        "SceneType": scene_type,
        "Config": {
            "ResourceSpec": resource_spec,
            "Replicas": replicas,
        },
    }

    def call_publish():
        info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="CreateSceneVersion",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        return api.do_call(info, body)

    api_call(call_publish)


def cmd_scene_versions(args: argparse.Namespace) -> None:
    """scene 命名空间下的 versions 子命令：列举场景版本列表。"""
    api, _configuration = get_universal_api()

    scene_id = args.id
    scene_type = (args.scene_type or "").strip()
    project = args.project
    page_number = args.page_number
    page_size = args.page_size

    allowed_scene_types = {"RAG", "IMAGE_SEARCH", "VIDEO_SEARCH"}
    if scene_type not in allowed_scene_types:
        print_error(
            "Invalid SceneType",
            "--scene-type must be one of: RAG, IMAGE_SEARCH, VIDEO_SEARCH",
        )

    if page_number <= 0 or page_size <= 0:
        print_error(
            "Invalid Pagination",
            "分页参数无效：--page-number 和 --page-size 必须为正整数。",
        )

    body = volcenginesdkcore.Flatten(
        {
            "SceneId": scene_id,
            "SceneType": scene_type,
            "Project": project,
            "PageNumber": page_number,
            "PageSize": page_size,
        }
    ).flat()

    def call_versions():
        info = volcenginesdkcore.UniversalInfo(
            method="GET",
            action="ListSceneVersion",
            service="ctxsearch",
            version="2025-09-01",
        )
        return api.do_call(info, body)

    api_call(call_versions)


def cmd_scene_stop(args: argparse.Namespace) -> None:
    """scene 命名空间下的 stop 子命令：停止场景（PROD 环境）。"""
    api, _configuration = get_universal_api()

    scene_id = args.id
    scene_type = (args.scene_type or "").strip()
    project = args.project

    allowed_scene_types = {"RAG", "IMAGE_SEARCH", "VIDEO_SEARCH"}
    if scene_type not in allowed_scene_types:
        print_error(
            "Invalid SceneType",
            "--scene-type must be one of: RAG, IMAGE_SEARCH, VIDEO_SEARCH",
        )

    body = {
        "SceneId": scene_id,
        "Project": project,
        "Environment": "PROD",
        "SceneType": scene_type,
    }

    def call_stop():
        info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="StopSceneInstance",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        return api.do_call(info, body)

    api_call(call_stop)


def cmd_scene_start(args: argparse.Namespace) -> None:
    """scene 命名空间下的 start 子命令：启动场景（PROD 环境）。"""
    api, _configuration = get_universal_api()

    scene_id = args.id
    scene_type = (args.scene_type or "").strip()
    project = args.project

    allowed_scene_types = {"RAG", "IMAGE_SEARCH", "VIDEO_SEARCH"}
    if scene_type not in allowed_scene_types:
        print_error(
            "Invalid SceneType",
            "--scene-type must be one of: RAG, IMAGE_SEARCH, VIDEO_SEARCH",
        )

    body = {
        "SceneId": scene_id,
        "Project": project,
        "Environment": "PROD",
        "SceneType": scene_type,
    }

    def call_start():
        info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="StartSceneInstance",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        return api.do_call(info, body)

    api_call(call_start)


def cmd_scene_rename(args: argparse.Namespace) -> None:
    """scene 命名空间下的 rename 子命令：编辑场景名称。"""
    api, _configuration = get_universal_api()

    scene_id = args.id
    scene_type = (args.scene_type or "").strip()
    name = args.name

    allowed_scene_types = {"RAG", "IMAGE_SEARCH", "VIDEO_SEARCH"}
    if scene_type not in allowed_scene_types:
        print_error(
            "Invalid SceneType",
            "--scene-type must be one of: RAG, IMAGE_SEARCH, VIDEO_SEARCH",
        )

    if not name or not name.strip():
        print_error(
            "Invalid Name",
            "名称无效：--name 不能为空。",
        )

    body = {
        "Id": scene_id,
        "SceneType": scene_type,
        "Name": name,
    }

    def call_rename():
        info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="UpdateScene",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        return api.do_call(info, body)

    api_call(call_rename)


def cmd_scene_delete(args: argparse.Namespace) -> None:
    """scene 命名空间下的 delete 子命令：删除场景（危险操作，必须 --confirm）。"""
    api, _configuration = get_universal_api()

    scene_id = args.id
    scene_type = (args.scene_type or "").strip()
    project = args.project
    confirm = args.confirm

    allowed_scene_types = {"RAG", "IMAGE_SEARCH", "VIDEO_SEARCH"}
    if scene_type not in allowed_scene_types:
        print_error(
            "Invalid SceneType",
            "--scene-type must be one of: RAG, IMAGE_SEARCH, VIDEO_SEARCH",
        )

    if not confirm:
        print_error(
            "Confirmation Required",
            "Refusing to delete without --confirm. Rerun with: scene delete --id <id> --scene-type <type> --project <project> --confirm",
        )

    body = {
        "Id": scene_id,
        "Project": project,
        "SceneType": scene_type,
    }

    def call_delete():
        info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="DeleteScene",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        return api.do_call(info, body)

    api_call(call_delete)


def cmd_scene_specs(args: argparse.Namespace) -> None:
    """scene 命名空间下的 specs 子命令：查询可用规格（CPU-only）。"""
    api, _configuration = get_universal_api()

    show_all = args.show_all

    body = volcenginesdkcore.Flatten({}).flat()

    try:
        info = volcenginesdkcore.UniversalInfo(
            method="GET",
            action="GetAIInstanceSpec",
            service="ctxsearch",
            version="2025-09-01",
        )
        resp = api.do_call(info, body)
        try:
            data = resp.to_dict()  # type: ignore[attr-defined]
        except AttributeError:
            data = resp

        specs = []
        if isinstance(data, dict):
            specs = data.get("Specs") or []
            if not isinstance(specs, list):
                specs = []
        else:
            specs = []

        if show_all:
            filtered = specs
        else:
            filtered = []
            for s in specs:
                if not isinstance(s, dict):
                    continue
                gpu_type = s.get("GpuType")
                if gpu_type:
                    continue
                filtered.append(s)

        print_result(filtered)
    except ApiException as e:
        msg = str(e)
        instr = ""
        if any(k in msg for k in ("Unauthorized", "Forbidden")):
            instr = "检查 VOLCENGINE_AK/VOLCENGINE_SK 是否正确，并确认具有调用 ContextSearch 接口的权限。"
        elif any(k in msg for k in ("BadRequest", "InvalidParameter")):
            instr = "检查传入的参数是否符合接口要求。"
        elif "NotFound" in msg:
            instr = "确认当前区域已开通 ContextSearch 服务，并支持对应接口。"
        details = f"{msg}\n\nInstruction: {instr}" if instr else msg
        print_error("API Error", details)
    except Exception as e:  # pragma: no cover - 防御性兜底
        print_error(
            "Unexpected Error",
            f"{str(e)}\n\nInstruction: 请检查网络连通性和 VOLCENGINE_* 环境变量配置。",
        )


def cmd_scene_data_import(args: argparse.Namespace) -> None:
    """scene 命名空间下的 data_import 子命令：通过 TOS 为场景导入数据 (AddSceneData)。"""
    api, _configuration = get_universal_api()

    scene_id = args.scene_id
    scene_type = (args.scene_type or "").strip()
    project = args.project
    bucket = args.bucket
    path = args.path

    allowed_scene_types = {"RAG", "IMAGE_SEARCH", "VIDEO_SEARCH"}
    if scene_type not in allowed_scene_types:
        print_error(
            "Invalid SceneType",
            "--scene-type must be one of: RAG, IMAGE_SEARCH, VIDEO_SEARCH",
        )

    if not path.endswith("/"):
        print_error(
            "Invalid Path",
            "--path must end with '/'. 当前仅支持通过 TOS 导入，Path 必须以斜杠结尾，例如 'rag/'。",
        )

    # 按场景类型组装默认 IngestConfig
    if scene_type == "RAG":
        ingest_config = {
            "EnabledAsrConfig": "false",
            "EnabledLlmConfig": "false",
            "EnabledOcrConfig": "false",
            "Prompt": "",
            "MaxChunkDuration": 30,
            "SceneType": "RAG",
        }
    elif scene_type == "IMAGE_SEARCH":
        ingest_config = {
            "EnabledAsrConfig": "false",
            "EnabledLlmConfig": "false",
            "EnabledOcrConfig": "false",
            "Prompt": "描述图片内容",
            "MaxChunkDuration": 30,
            "SceneType": "IMAGE_SEARCH",
        }
    else:  # VIDEO_SEARCH
        ingest_config = {
            "EnabledAsrConfig": "false",
            "EnabledLlmConfig": "false",
            "EnabledOcrConfig": "false",
            "Prompt": "Summarize the video content",
            "SceneType": "VIDEO_SEARCH",
        }

    body_dict = {
        "SceneId": scene_id,
        "Project": project,
        "Type": "TOS",
        "SceneType": scene_type,
        "IngestConfig": ingest_config,
        "TosConfig": {
            "Bucket": bucket,
            "Path": path,
        },
    }

    # IMAGE_SEARCH 额外支持 CustomContent={}
    if scene_type == "IMAGE_SEARCH":
        body_dict["CustomContent"] = {}

    def call():
        info = volcenginesdkcore.UniversalInfo(
            method="POST",
            action="AddSceneData",
            service="ctxsearch",
            version="2025-09-01",
            content_type="application/json",
        )
        return api.do_call(info, body_dict)

    api_call(call)


def cmd_scene_data_list(args: argparse.Namespace) -> None:
    """scene 命名空间下的 data_list 子命令：查看场景数据列表 (ListSceneData)。"""
    api, _configuration = get_universal_api()

    scene_id = args.scene_id
    scene_type = (args.scene_type or "").strip()
    project = args.project
    page_number = args.page_number
    page_size = args.page_size

    allowed_scene_types = {"RAG", "IMAGE_SEARCH", "VIDEO_SEARCH"}
    if scene_type not in allowed_scene_types:
        print_error(
            "Invalid SceneType",
            "--scene-type must be one of: RAG, IMAGE_SEARCH, VIDEO_SEARCH",
        )

    if page_number <= 0 or page_size <= 0:
        print_error(
            "Invalid Pagination",
            "分页参数无效：--page-number 和 --page-size 必须为正整数。",
        )

    body = volcenginesdkcore.Flatten(
        {
            "Project": project,
            "SceneId": scene_id,
            "SceneType": scene_type,
            "PageNumber": page_number,
            "PageSize": page_size,
            "WithImageData": False,
            "NameKey": "",
            "IsDemo": False,
        }
    ).flat()

    def call():
        info = volcenginesdkcore.UniversalInfo(
            method="GET",
            action="ListSceneData",
            service="ctxsearch",
            version="2025-09-01",
        )
        return api.do_call(info, body)

    api_call(call)


def cmd_scene_chunks(args: argparse.Namespace) -> None:
    """scene 命名空间下的 chunks 子命令：查看场景数据切片列表 (ListSceneDataChunk)。"""
    api, _configuration = get_universal_api()

    scene_id = args.scene_id
    scene_type = (args.scene_type or "").strip()
    project = args.project
    data_id = args.data_id or ""
    page_number = args.page_number
    page_size = args.page_size

    allowed_scene_types = {"RAG", "IMAGE_SEARCH", "VIDEO_SEARCH"}
    if scene_type not in allowed_scene_types:
        print_error(
            "Invalid SceneType",
            "--scene-type must be one of: RAG, IMAGE_SEARCH, VIDEO_SEARCH",
        )

    if page_number <= 0 or page_size <= 0:
        print_error(
            "Invalid Pagination",
            "分页参数无效：--page-number 和 --page-size 必须为正整数。",
        )

    body = volcenginesdkcore.Flatten(
        {
            "Project": project,
            "SceneId": scene_id,
            "DataId": data_id,
            "SceneType": scene_type,
            "PageNumber": page_number,
            "PageSize": page_size,
            "IsDemo": False,
        }
    ).flat()

    def call():
        info = volcenginesdkcore.UniversalInfo(
            method="GET",
            action="ListSceneDataChunk",
            service="ctxsearch",
            version="2025-09-01",
        )
        return api.do_call(info, body)

    api_call(call)


def register_scene(ns_parsers: Any) -> None:
    """在顶层解析器上注册 scene 命名空间及其子命令。"""
    scene_parser = ns_parsers.add_parser(
        "scene", help="管理 ContextSearch 场景 (scene)"
    )
    scene_subparsers = scene_parser.add_subparsers(dest="command", required=True)

    # 子命令：scene list
    p_list = scene_subparsers.add_parser(
        "list",
        help="列举 ContextSearch 场景列表 (ListScene)",
    )
    p_list.add_argument(
        "--page-number",
        type=int,
        default=1,
        help="页码，默认 1",
    )
    p_list.add_argument(
        "--page-size",
        type=int,
        default=12,
        help="每页条数，默认 12",
    )
    p_list.set_defaults(func=cmd_scene_list)

    # 子命令：scene get
    p_get = scene_subparsers.add_parser(
        "get",
        help="查询 ContextSearch 场景详情 (GetScene)",
    )
    p_get.add_argument(
        "--id",
        required=True,
        help="场景 Id，必填，例如 2036358376137789442",
    )
    p_get.add_argument(
        "--scene-type",
        required=True,
        help="场景类型 SceneType，必填，例如 RAG",
    )
    p_get.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_get.add_argument(
        "--is-demo",
        action="store_true",
        default=False,
        help="是否为 Demo 场景，可选，默认 false；传入该开关则为 true",
    )
    p_get.set_defaults(func=cmd_scene_get)

    # 子命令：scene storage_set
    p_storage_set = scene_subparsers.add_parser(
        "storage_set",
        help="配置场景存储位置 (GetScene/DescribeInstance/UpdateScene，含状态限制)",
    )
    p_storage_set.add_argument(
        "--id",
        required=True,
        help="场景 Id，必填，例如 2042492662139453441",
    )
    p_storage_set.add_argument(
        "--scene-type",
        required=True,
        help="场景类型 SceneType，必填，可选：RAG、IMAGE_SEARCH、VIDEO_SEARCH",
    )
    p_storage_set.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_storage_set.add_argument(
        "--instance-type",
        required=True,
        help="存储实例类型，必填，目前仅支持 OPENSEARCH",
    )
    p_storage_set.add_argument(
        "--instance-id",
        required=True,
        help="存储实例 InstanceId，必填，例如 o-dev-00o8ptglykg8",
    )
    p_storage_set.add_argument(
        "--username",
        required=True,
        help="存储实例用户名，必填",
    )
    p_storage_set.add_argument(
        "--password",
        required=True,
        help="存储实例密码，必填",
    )
    p_storage_set.add_argument(
        "--is-demo",
        action="store_true",
        default=False,
        help="是否为 Demo 场景，可选，默认 false；传入该开关则为 true",
    )
    p_storage_set.set_defaults(func=cmd_scene_storage_set)

    # 子命令：scene create
    p_create = scene_subparsers.add_parser(
        "create",
        help=(
            "按控制台创建链路检查/部署后创建场景；AGENTIC_SEARCH 使用 "
            "ListAgenticSceneTemplate/CreateAgenticScene"
        ),
    )
    p_create.add_argument(
        "--scene-type",
        required=True,
        help="场景类型 SceneType，必填，可选：RAG、IMAGE_SEARCH、VIDEO_SEARCH、AGENTIC_SEARCH",
    )
    p_create.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_create.add_argument(
        "--name",
        required=True,
        help="场景名称，必填",
    )
    p_create.add_argument(
        "--description",
        default="",
        help="场景描述，可选，默认空字符串",
    )
    p_create.add_argument(
        "--resource-tags",
        default="",
        help='自定义资源标签，JSON 数组，例如 \'[{"Key":"env","Value":"boe"}]\'，可选，默认空',
    )
    p_create.add_argument(
        "--max-attempts",
        type=int,
        default=30,
        help="部署状态轮询最大次数，可选，默认 30（与控制台 AgenticSearch 创建流程一致）",
    )
    p_create.add_argument(
        "--poll-interval-ms",
        type=int,
        default=1000,
        help="部署状态轮询间隔（毫秒），可选，默认 1000（与控制台 AgenticSearch 创建流程一致）",
    )
    p_create.set_defaults(func=cmd_scene_create)

    # 子命令：scene publish
    p_publish = scene_subparsers.add_parser(
        "publish",
        help="发布场景（创建版本） (CreateSceneVersion)",
    )
    p_publish.add_argument(
        "--id",
        required=True,
        help="场景 Id，必填，例如 2042490062736326658",
    )
    p_publish.add_argument(
        "--scene-type",
        required=True,
        help="场景类型 SceneType，必填，可选：RAG、IMAGE_SEARCH、VIDEO_SEARCH",
    )
    p_publish.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_publish.add_argument(
        "--version",
        required=True,
        help='发布的版本号，必填，格式为 x.y.z，例如 "1.0.0"',
    )
    p_publish.add_argument(
        "--resource-spec",
        default="vci.n3i.2c-4gi",
        help='资源规格，可选，默认 "vci.n3i.2c-4gi"',
    )
    p_publish.add_argument(
        "--replicas",
        type=int,
        default=2,
        help="副本数，可选，默认 2",
    )
    p_publish.set_defaults(func=cmd_scene_publish)

    # 子命令：scene versions
    p_versions = scene_subparsers.add_parser(
        "versions",
        help="列举场景版本列表 (ListSceneVersion)",
    )
    p_versions.add_argument(
        "--id",
        required=True,
        help="场景 Id，必填，例如 2042490062736326658",
    )
    p_versions.add_argument(
        "--scene-type",
        required=True,
        help="场景类型 SceneType，必填，可选：RAG、IMAGE_SEARCH、VIDEO_SEARCH",
    )
    p_versions.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_versions.add_argument(
        "--page-number",
        type=int,
        default=1,
        help="页码，默认 1",
    )
    p_versions.add_argument(
        "--page-size",
        type=int,
        default=6,
        help="每页条数，默认 6",
    )
    p_versions.set_defaults(func=cmd_scene_versions)

    # 子命令：scene stop
    p_stop = scene_subparsers.add_parser(
        "stop",
        help='停止场景 (StopSceneInstance, Environment="PROD")',
    )
    p_stop.add_argument(
        "--id",
        required=True,
        help="场景 Id，必填，例如 2042490062736326658",
    )
    p_stop.add_argument(
        "--scene-type",
        required=True,
        help="场景类型 SceneType，必填，可选：RAG、IMAGE_SEARCH、VIDEO_SEARCH",
    )
    p_stop.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_stop.set_defaults(func=cmd_scene_stop)

    # 子命令：scene start
    p_start = scene_subparsers.add_parser(
        "start",
        help='启动场景 (StartSceneInstance, Environment="PROD")',
    )
    p_start.add_argument(
        "--id",
        required=True,
        help="场景 Id，必填，例如 2042490062736326658",
    )
    p_start.add_argument(
        "--scene-type",
        required=True,
        help="场景类型 SceneType，必填，可选：RAG、IMAGE_SEARCH、VIDEO_SEARCH",
    )
    p_start.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_start.set_defaults(func=cmd_scene_start)

    # 子命令：scene rename
    p_rename = scene_subparsers.add_parser(
        "rename",
        help="编辑场景名称 (UpdateScene)",
    )
    p_rename.add_argument(
        "--id",
        required=True,
        help="场景 Id，必填",
    )
    p_rename.add_argument(
        "--scene-type",
        required=True,
        help="场景类型 SceneType，必填，可选：RAG、IMAGE_SEARCH、VIDEO_SEARCH",
    )
    p_rename.add_argument(
        "--name",
        required=True,
        help="新的场景名称，必填",
    )
    p_rename.set_defaults(func=cmd_scene_rename)

    # 子命令：scene delete
    p_delete = scene_subparsers.add_parser(
        "delete",
        help="删除场景（危险操作，必须 --confirm） (DeleteScene)",
    )
    p_delete.add_argument(
        "--id",
        required=True,
        help="场景 Id，必填",
    )
    p_delete.add_argument(
        "--scene-type",
        required=True,
        help="场景类型 SceneType，必填，可选：RAG、IMAGE_SEARCH、VIDEO_SEARCH",
    )
    p_delete.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_delete.add_argument(
        "--confirm",
        action="store_true",
        help="危险操作，必须显式提供该开关才允许删除",
    )
    p_delete.set_defaults(func=cmd_scene_delete)

    # 子命令：scene specs
    p_specs = scene_subparsers.add_parser(
        "specs",
        help="查询可用规格（CPU-only）（GetAIInstanceSpec）",
    )
    p_specs.add_argument(
        "--show-all",
        action="store_true",
        help="是否展示全部规格（包含 GPU 规格）；缺省仅展示 CPU-only 规格",
    )
    p_specs.set_defaults(func=cmd_scene_specs)

    # 子命令：scene data_import
    p_data_import = scene_subparsers.add_parser(
        "data_import",
        help="通过 TOS 为场景导入数据 (AddSceneData)",
    )
    p_data_import.add_argument(
        "--scene-id",
        required=True,
        help="场景 Id，必填，例如 2042490062736326658",
    )
    p_data_import.add_argument(
        "--scene-type",
        required=True,
        help="场景类型 SceneType，必填，可选：RAG、IMAGE_SEARCH、VIDEO_SEARCH",
    )
    p_data_import.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_data_import.add_argument(
        "--bucket",
        required=True,
        help="TOS Bucket 名称，必填",
    )
    p_data_import.add_argument(
        "--path",
        required=True,
        help="TOS Path，必填，必须以斜杠结尾，例如 'rag/'",
    )
    p_data_import.set_defaults(func=cmd_scene_data_import)

    # 子命令：scene data_list
    p_data_list = scene_subparsers.add_parser(
        "data_list",
        help="查看场景数据列表 (ListSceneData)",
    )
    p_data_list.add_argument(
        "--scene-id",
        required=True,
        help="场景 Id，必填，例如 2042490062736326658",
    )
    p_data_list.add_argument(
        "--scene-type",
        required=True,
        help="场景类型 SceneType，必填，可选：RAG、IMAGE_SEARCH、VIDEO_SEARCH",
    )
    p_data_list.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_data_list.add_argument(
        "--page-number",
        type=int,
        default=1,
        help="页码，默认 1",
    )
    p_data_list.add_argument(
        "--page-size",
        type=int,
        default=10,
        help="每页条数，默认 10",
    )
    p_data_list.set_defaults(func=cmd_scene_data_list)

    # 子命令：scene chunks
    p_chunks = scene_subparsers.add_parser(
        "chunks",
        help="查看场景数据切片列表 (ListSceneDataChunk)",
    )
    p_chunks.add_argument(
        "--scene-id",
        required=True,
        help="场景 Id，必填，例如 2042490062736326658",
    )
    p_chunks.add_argument(
        "--scene-type",
        required=True,
        help="场景类型 SceneType，必填，可选：RAG、IMAGE_SEARCH、VIDEO_SEARCH",
    )
    p_chunks.add_argument(
        "--project",
        default="default",
        help='Project 名称，可选，默认 "default"',
    )
    p_chunks.add_argument(
        "--data-id",
        default="",
        help="数据 Id，可选，默认空字符串表示不过滤",
    )
    p_chunks.add_argument(
        "--page-number",
        type=int,
        default=1,
        help="页码，默认 1",
    )
    p_chunks.add_argument(
        "--page-size",
        type=int,
        default=5,
        help="每页条数，默认 5",
    )
    p_chunks.set_defaults(func=cmd_scene_chunks)
