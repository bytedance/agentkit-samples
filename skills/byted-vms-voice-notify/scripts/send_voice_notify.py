# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""byted-vms-voice-notify · 火山云通信语音通知 Skill 脚本.

封装的 TOP Action:
    语音任务下发:
    - SingleBatchAppend      single_append
    - CreateTask             create_task
    - BatchAppend            batch_append          已创建任务追加号码 (单次最多 1 万)
    - PauseTask              pause_task            暂停批量任务
    - ResumeTask             resume_task           恢复批量任务
    - StopTask               stop_task             停止批量任务
    - UpdateTask             update_task           更新批量任务时间窗 / 并发 / 重呼策略
    - QuerySingleInfo        query_single          按 SingleOpenId 查单次发送结果
    - SingleCancel           cancel_single         按 SingleOpenId 取消单次发送
    号码池:
    - NumberPoolList         list_number_pool
    TTS 模板生命周期:
    - OpenCreateTts          open_create_tts
    - OpenDeleteResource     delete_tts            (TOP 无 OpenDeleteTts; 直接复用通用删)
                                                    TTS 模板平台不支持改文案/改名,
                                                    需调整请到控制台手工修改并重审.
    录音文件管理:
    - (无 OpenCreateVoice)   create_voice          已弃用; 调用返回 ApiNotSupported + 直传引导
    - OpenDeleteVoice        delete_voice          删除录音文件
    - QueryOpenGetResource   query_voice           查录音文件 (Type=0)
    - GetResourceUploadUrl   get_upload_url        申请录音文件直传 URL
    - OpenSubmitUpload       submit_upload         上传完成后提交录音注册
    通用资源:
    - QueryOpenGetResource   list_resource         录音/TTS/IVR 资源列表 (统一入口)
    - QueryUsableResource    list_usable           查可用 (审核通过) 资源
    - OpenUpdateResource     update_resource       改资源 Name (录音/IVR; TTS 不支持改名)
    - OpenDeleteResource     delete_resource       通用删资源 (TTS 用 delete_tts)

注: TTS 模板的查询统一通过 list_resource --type 1 (可选 --resource-key 过滤) 完成.

仅依赖同目录下 _topclient.py, 不跨 skill 包 import.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _topclient import call_top, emit, fail  # noqa: E402


def cmd_list_resource(args: argparse.Namespace) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "ServiceType": 100,
        "SubServiceType": args.sub_service_type,
        "Type": args.type if args.type is not None else 0,
        "Limit": args.limit,
        "Offset": args.offset,
    }
    resp = call_top("QueryOpenGetResource", body)
    if args.keyword or args.resource_key:
        result = resp.get("Result") or {}
        records = result.get("Records") or []
        kw = (args.keyword or "").lower()

        def _match(r: Dict[str, Any]) -> bool:
            if args.resource_key and r.get("ResourceKey") != args.resource_key:
                return False
            if not kw:
                return True
            for f in ("Name", "Remark", "TtsTemplateContent", "Lang"):
                v = r.get(f)
                if v and kw in str(v).lower():
                    return True
            return False
        result["Records"] = [r for r in records if _match(r)]
        resp["Result"] = result
    return resp


def cmd_list_number_pool(args: argparse.Namespace) -> Dict[str, Any]:
    return call_top("NumberPoolList", {
        "SubServiceType": args.sub_service_type,
        "Limit": args.limit,
        "Offset": args.offset,
    }, form=True)


def cmd_single_append(args: argparse.Namespace) -> Dict[str, Any]:
    single: Dict[str, Any] = {
        "Phone": args.phone,
        "Type": args.type,
        "Resource": args.resource,
        "NumberPoolNo": args.number_pool_no,
        "SingleOpenId": args.single_open_id or uuid.uuid4().hex,
    }
    if args.number_list:
        single["NumberList"] = args.number_list.split(",")
    if args.ring_again_times is not None:
        single["RingAgainTimes"] = args.ring_again_times
    if args.ring_again_interval is not None:
        single["RingAgainInterval"] = args.ring_again_interval
    if args.number_type is not None:
        single["NumberType"] = args.number_type
    if args.ext:
        single["Ext"] = args.ext
    if args.phone_param:
        single["PhoneParam"] = json.loads(args.phone_param)
    if args.trigger_time:
        single["TriggerTime"] = args.trigger_time
    if args.forbid_time_list:
        single["ForbidTimeList"] = json.loads(args.forbid_time_list)
    return call_top("SingleBatchAppend", {"List": [single]})


def cmd_create_task(args: argparse.Namespace) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "Name": args.name,
        "Type": args.type,
        "Resource": args.resource,
        "NumberPoolNo": args.number_pool_no,
        "StartTime": args.start_time,
        "EndTime": args.end_time,
        "Concurrency": args.concurrency,
        # SelectNumberRule 是服务端必填: 1=随机选号 (默认) / 2=轮询 / 3=尾号匹配
        "SelectNumberRule": args.select_number_rule,
    }
    if args.phone_list_json:
        body["PhoneList"] = json.loads(args.phone_list_json)
    if args.number_list:
        body["NumberList"] = args.number_list.split(",")
    if args.start is not None:
        body["Start"] = args.start
    if args.max_ring_duration is not None:
        body["MaxRingDuration"] = args.max_ring_duration
    if args.ring_again_times is not None:
        body["RingAgainTimes"] = args.ring_again_times
    if args.ring_again_interval is not None:
        body["RingAgainInterval"] = args.ring_again_interval
    if args.forbid_time_list:
        body["ForbidTimeList"] = json.loads(args.forbid_time_list)
    return call_top("CreateTask", body)


def cmd_open_create_tts(args: argparse.Namespace) -> Dict[str, Any]:
    # OpenCreateTts 服务端必填: TtsTemplateContent + Name; Lang 缺省按 zh 处理.
    if not args.content or not args.content.strip():
        return {
            "ok": False,
            "errorCode": "RequestParametersError",
            "message": "--content 不能为空: TTS 模板文案为必填",
            "requestId": None,
            "suggest": "请通过 --content 传入模板文案",
        }
    if not args.name or not args.name.strip():
        return {
            "ok": False,
            "errorCode": "RequestParametersError",
            "message": "--name 不能为空: TTS 模板名称为必填",
            "requestId": None,
            "suggest": "请通过 --name 传入模板名称 (服务端必填)",
        }
    body: Dict[str, Any] = {
        "TtsTemplateContent": args.content,
        "Name": args.name,
        "Lang": args.lang or "zh",
    }
    if args.remark:
        body["Remark"] = args.remark
    return call_top("OpenCreateTts", body)


def cmd_delete_tts(args: argparse.Namespace) -> Dict[str, Any]:
    """删除 TTS 模板 (OpenDeleteResource).

    TOP 没有独立的 OpenDeleteTts 接口, 直接复用通用 OpenDeleteResource.
    """
    return call_top("OpenDeleteResource", {"ResourceKey": args.resource_key})


# ---------- 录音文件管理 (从 byted-vms-configure 迁移而来) ----------

def cmd_create_voice(args: argparse.Namespace) -> Dict[str, Any]:
    """创建录音文件: TOP 没有 OpenCreateVoice, 必须走直传流程.

    返回引导信息, 提示 Agent / 用户使用 ``get_upload_url`` + ``submit_upload``
    两步法注册录音; 也可前往控制台手工上传:
    https://console.volcengine.com/cloud_vms/voice-file
    """
    return {
        "ok": False,
        "errorCode": "ApiNotSupported",
        "message": "TOP 不提供 OpenCreateVoice (公网 URL 创建录音) 的开放接口",
        "requestId": None,
        "suggest": (
            "请改用录音直传两步法:\n"
            "  1) python3 scripts/send_voice_notify.py get_upload_url "
            "--file-name <name.wav> [--content-type audio/wav] "
            "[--sub-service-type 102]\n"
            "  2) 客户端用返回的 UploadUrl PUT 文件 "
            "(curl -X PUT --data-binary @file '<UploadUrl>')\n"
            "  3) python3 scripts/send_voice_notify.py submit_upload "
            "--upload-id <UploadId> --name <展示名> [--sub-service-type 102]\n"
            "或前往控制台手工上传: "
            "https://console.volcengine.com/cloud_vms/voice-file"
        ),
    }


def cmd_query_voice(args: argparse.Namespace) -> Dict[str, Any]:
    """查录音文件. 平台没有 OpenQueryVoice, 复用 QueryOpenGetResource(Type=0)."""
    body: Dict[str, Any] = {
        "ServiceType": 100,
        "SubServiceType": args.sub_service_type,
        "Type": 0,
        "Limit": args.limit,
        "Offset": args.offset,
    }
    resp = call_top("QueryOpenGetResource", body)
    if args.resource_key or args.name:
        result = resp.get("Result") or {}
        records = result.get("Records") or []

        def _match(r: Dict[str, Any]) -> bool:
            if args.resource_key and r.get("ResourceKey") != args.resource_key:
                return False
            if args.name and args.name.lower() not in str(r.get("Name") or "").lower():
                return False
            return True
        result["Records"] = [r for r in records if _match(r)]
        resp["Result"] = result
    return resp


def cmd_delete_voice(args: argparse.Namespace) -> Dict[str, Any]:
    """删除录音文件 (OpenDeleteVoice)."""
    return call_top("OpenDeleteVoice", {"ResourceKey": args.resource_key})


def cmd_get_upload_url(args: argparse.Namespace) -> Dict[str, Any]:
    """申请录音文件直传 URL (GetResourceUploadUrl).

    流程: get_upload_url 拿到 UploadUrl + UploadId → 客户端 PUT 文件到 UploadUrl
    → submit_upload 用 UploadId 注册资源.
    """
    body: Dict[str, Any] = {"FileName": args.file_name}
    if args.sub_service_type is not None:
        body["SubServiceType"] = args.sub_service_type
    if args.content_type:
        body["ContentType"] = args.content_type
    return call_top("GetResourceUploadUrl", body)


def cmd_submit_upload(args: argparse.Namespace) -> Dict[str, Any]:
    """提交直传完成 (OpenSubmitUpload), 把已上传的录音注册成正式资源."""
    body: Dict[str, Any] = {
        "UploadId": args.upload_id,
        "Name": args.name,
    }
    if args.sub_service_type is not None:
        body["SubServiceType"] = args.sub_service_type
    if args.remark:
        body["Remark"] = args.remark
    if args.lang:
        body["Lang"] = args.lang
    return call_top("OpenSubmitUpload", body)


# ---------- 通用资源管理 (从 byted-vms-configure 迁移而来) ----------

def cmd_list_usable(args: argparse.Namespace) -> Dict[str, Any]:
    """查可用 (审核通过) 资源 QueryUsableResource. SDK 走 GET, Type 必填."""
    return call_top("QueryUsableResource", {"Type": args.type}, method="GET")


def cmd_update_resource(args: argparse.Namespace) -> Dict[str, Any]:
    """改录音/IVR Name (OpenUpdateResource, form POST). TTS 模板不支持改名."""
    return call_top("OpenUpdateResource",
                    {"ResourceKey": args.resource_key, "Name": args.name},
                    form=True)


def cmd_delete_resource(args: argparse.Namespace) -> Dict[str, Any]:
    """通用资源删除 (OpenDeleteResource). TTS 请用 delete_tts."""
    return call_top("OpenDeleteResource", {"ResourceKey": args.resource_key})


# ---------- 任务运维: 追加 / 暂停 / 恢复 / 停止 / 更新 ----------

def cmd_batch_append(args: argparse.Namespace) -> Dict[str, Any]:
    """向已创建的批量任务追加号码 (PhoneList 单次最多 1 万条)."""
    if args.phone_list_json:
        phone_list = json.loads(args.phone_list_json)
    else:
        phone_list = [{"Phone": p.strip()} for p in args.phones.split(",") if p.strip()]
    return call_top("BatchAppend", {
        "TaskOpenId": args.task_open_id,
        "PhoneList": phone_list,
    })


def cmd_pause_task(args: argparse.Namespace) -> Dict[str, Any]:
    return call_top("PauseTask", {"TaskOpenId": args.task_open_id}, form=True)


def cmd_resume_task(args: argparse.Namespace) -> Dict[str, Any]:
    return call_top("ResumeTask", {"TaskOpenId": args.task_open_id}, form=True)


def cmd_stop_task(args: argparse.Namespace) -> Dict[str, Any]:
    return call_top("StopTask", {"TaskOpenId": args.task_open_id}, form=True)


def cmd_update_task(args: argparse.Namespace) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "TaskOpenId": args.task_open_id,
        "StartTime": args.start_time,
        "EndTime": args.end_time,
        "Concurrency": args.concurrency,
    }
    if args.ring_again_times is not None:
        body["RingAgainTimes"] = args.ring_again_times
    if args.ring_again_interval is not None:
        body["RingAgainInterval"] = args.ring_again_interval
    if args.forbid_time_list:
        body["ForbidTimeList"] = json.loads(args.forbid_time_list)
    if args.recall is not None:
        body["Recall"] = args.recall
    return call_top("UpdateTask", body)


# ---------- 单次发送查询 / 取消 ----------

def cmd_query_single(args: argparse.Namespace) -> Dict[str, Any]:
    """按 SingleOpenId 查单次发送的状态、通话时长、CallUuid."""
    return call_top("QuerySingleInfo", {"SingleOpenId": args.single_open_id},
                    method="GET")


def cmd_cancel_single(args: argparse.Namespace) -> Dict[str, Any]:
    """按 SingleOpenId 取消尚未触发或重呼中的单次发送."""
    return call_top("SingleCancel", {"SingleOpenId": args.single_open_id},
                    method="GET")


_ACTIONS = {
    "list_resource": cmd_list_resource,
    "list_number_pool": cmd_list_number_pool,
    "single_append": cmd_single_append,
    "create_task": cmd_create_task,
    "open_create_tts": cmd_open_create_tts,
    "delete_tts": cmd_delete_tts,
    "create_voice": cmd_create_voice,
    "query_voice": cmd_query_voice,
    "delete_voice": cmd_delete_voice,
    "get_upload_url": cmd_get_upload_url,
    "submit_upload": cmd_submit_upload,
    "list_usable": cmd_list_usable,
    "update_resource": cmd_update_resource,
    "delete_resource": cmd_delete_resource,
    "batch_append": cmd_batch_append,
    "pause_task": cmd_pause_task,
    "resume_task": cmd_resume_task,
    "stop_task": cmd_stop_task,
    "update_task": cmd_update_task,
    "query_single": cmd_query_single,
    "cancel_single": cmd_cancel_single,
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="byted-vms-voice-notify · 火山云通信语音通知")
    sub = p.add_subparsers(dest="action", required=True)

    sp = sub.add_parser("list_resource", help="查询语音资源 (GetVoiceResourceList)")
    sp.add_argument("--sub-service-type", type=int, default=102, help="102=语音通知 103=智能外呼 (必填)")
    sp.add_argument("--type", type=int, choices=[0, 1, 2], help="0录音 1TTS 2IVR")
    sp.add_argument("--keyword", help="按 Name/Remark/TtsTemplateContent/Lang 模糊过滤")
    sp.add_argument("--resource-key",
                    help="按 ResourceKey 精确过滤 (用于查单条 TTS/录音详情, 替代旧的 query_tts)")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--offset", type=int, default=0)

    sp = sub.add_parser("list_number_pool", help="查询号码池 (NumberPoolList)")
    sp.add_argument("--sub-service-type", type=int, default=102, help="102=语音通知 103=智能外呼")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--offset", type=int, default=0)

    sp = sub.add_parser("single_append", help="单次发送 (SingleBatchAppend)")
    sp.add_argument("--phone", required=True)
    sp.add_argument("--resource", required=True, help="ResourceKey")
    sp.add_argument("--number-pool-no", required=True)
    sp.add_argument("--type", type=int, default=0, help="0录音 1TTS 2IVR")
    sp.add_argument("--single-open-id")
    sp.add_argument("--number-list", help="主叫号码列表, 逗号分隔")
    sp.add_argument("--ring-again-times", type=int)
    sp.add_argument("--ring-again-interval", type=int)
    sp.add_argument("--number-type", type=int)
    sp.add_argument("--ext")
    sp.add_argument("--phone-param", help="JSON, TTS/IVR 变量")
    sp.add_argument("--trigger-time", help="如 2026/05/28 11:11")
    sp.add_argument("--forbid-time-list", help="JSON 数组")

    sp = sub.add_parser("create_task", help="批量任务 (CreateTask)")
    sp.add_argument("--name", required=True)
    sp.add_argument("--type", type=int, required=True, help="0录音 1TTS模板 2IVR 3TTS")
    sp.add_argument("--resource", required=True)
    sp.add_argument("--number-pool-no", required=True)
    sp.add_argument("--start-time", required=True)
    sp.add_argument("--end-time", required=True)
    sp.add_argument("--concurrency", type=int, required=True)
    sp.add_argument("--select-number-rule", type=int, default=1,
                    help="服务端必填: 1=随机 (默认) / 2=轮询 / 3=尾号匹配")
    sp.add_argument("--phone-list-json", help="JSON 数组")
    sp.add_argument("--number-list", help="主叫号码列表, 逗号分隔")
    sp.add_argument("--start", type=lambda x: x.lower() == "true")
    sp.add_argument("--max-ring-duration", type=int)
    sp.add_argument("--ring-again-times", type=int)
    sp.add_argument("--ring-again-interval", type=int)
    sp.add_argument("--forbid-time-list", help="JSON 数组")

    sp = sub.add_parser("open_create_tts", help="在线创建 TTS 模板 (OpenCreateTts)")
    sp.add_argument("--content", required=True, help="模板文案 (必填)")
    sp.add_argument("--name", required=True, help="模板名称 (服务端必填)")
    sp.add_argument("--remark")
    sp.add_argument("--lang", default="zh", help="如 zh / en / jap, 默认 zh")

    sp = sub.add_parser("delete_tts", help="删除 TTS 模板 (走 OpenDeleteResource)")
    sp.add_argument("--resource-key", required=True)

    # 录音文件管理 (从 byted-vms-configure 迁移而来)
    sp = sub.add_parser("create_voice",
                        help="(已弃用) TOP 没有 OpenCreateVoice; 改用 get_upload_url+submit_upload")
    sp.add_argument("--name", required=True)
    sp.add_argument("--voice-url", required=True, help="录音文件 URL, 公网可访问")
    sp.add_argument("--remark")
    sp.add_argument("--lang")

    sp = sub.add_parser("query_voice", help="查询录音文件 (QueryOpenGetResource Type=0)")
    sp.add_argument("--sub-service-type", type=int, default=102,
                    help="102=语音通知 / 103=双呼 / 104=智能外呼; "
                         "见 references/vms-fundamentals.md §1")
    sp.add_argument("--resource-key", help="本地按 ResourceKey 精确过滤")
    sp.add_argument("--name", help="本地按 Name 模糊过滤")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--offset", type=int, default=0)

    sp = sub.add_parser("delete_voice", help="删除录音文件 (OpenDeleteVoice)")
    sp.add_argument("--resource-key", required=True)

    sp = sub.add_parser("get_upload_url",
                        help="申请录音直传 URL (GetResourceUploadUrl)")
    sp.add_argument("--file-name", required=True, help="录音文件名, 例如 hello.wav")
    sp.add_argument("--sub-service-type", type=int,
                    help="102=语音通知 / 103=双呼 / 104=智能外呼; "
                         "见 references/vms-fundamentals.md §1")
    sp.add_argument("--content-type", help="如 audio/wav, audio/mpeg")

    sp = sub.add_parser("submit_upload",
                        help="提交直传完成, 注册录音资源 (OpenSubmitUpload)")
    sp.add_argument("--upload-id", required=True, help="get_upload_url 返回的 UploadId")
    sp.add_argument("--name", required=True, help="录音展示名")
    sp.add_argument("--sub-service-type", type=int,
                    help="102=语音通知 / 103=双呼 / 104=智能外呼; "
                         "见 references/vms-fundamentals.md §1")
    sp.add_argument("--remark")
    sp.add_argument("--lang")

    # 通用资源 (从 byted-vms-configure 迁移而来)
    sp = sub.add_parser("list_usable",
                        help="查可用 (审核通过) 资源 (QueryUsableResource)")
    sp.add_argument("--type", type=int, required=True,
                    help="0=录音 1=TTS 2=IVR")

    sp = sub.add_parser("update_resource",
                        help="改录音/IVR Name (OpenUpdateResource); TTS 模板不支持改名")
    sp.add_argument("--resource-key", required=True)
    sp.add_argument("--name", required=True)

    sp = sub.add_parser("delete_resource",
                        help="通用资源删除 (OpenDeleteResource); TTS 请用 delete_tts")
    sp.add_argument("--resource-key", required=True)

    sp = sub.add_parser("batch_append",
                        help="向已有任务追加号码 (BatchAppend, 单次最多 1 万)")
    sp.add_argument("--task-open-id", required=True, help="任务唯一标识 TaskOpenId")
    sp.add_argument("--phones",
                    help="简易模式: 逗号分隔的手机号; 与 --phone-list-json 二选一")
    sp.add_argument("--phone-list-json",
                    help="完整模式: PhoneParam 数组 JSON, 如 [{\"Phone\":\"138...\","
                         "\"PhoneParam\":{\"name\":\"张三\"},\"TtsContent\":\"...\","
                         "\"Ext\":\"biz=overdue\"}]")

    sp = sub.add_parser("pause_task", help="暂停批量任务 (PauseTask)")
    sp.add_argument("--task-open-id", required=True)

    sp = sub.add_parser("resume_task", help="恢复批量任务 (ResumeTask)")
    sp.add_argument("--task-open-id", required=True)

    sp = sub.add_parser("stop_task", help="停止批量任务 (StopTask)")
    sp.add_argument("--task-open-id", required=True)

    sp = sub.add_parser("update_task",
                        help="更新批量任务的执行窗口 / 并发 / 重呼策略 (UpdateTask)")
    sp.add_argument("--task-open-id", required=True)
    sp.add_argument("--start-time", required=True,
                    help="任务开始时间, 格式 'YYYY-MM-DD HH:MM:SS'")
    sp.add_argument("--end-time", required=True)
    sp.add_argument("--concurrency", type=int, required=True)
    sp.add_argument("--ring-again-times", type=int)
    sp.add_argument("--ring-again-interval", type=int,
                    help="单位分钟, 最小 5")
    sp.add_argument("--forbid-time-list",
                    help="JSON 数组, ForbidTimeItem 列表")
    sp.add_argument("--recall", type=lambda x: x.lower() == "true",
                    help="是否更新重呼设置, 默认 true")

    sp = sub.add_parser("query_single",
                        help="按 SingleOpenId 查单次发送状态/时长/CallUuid (QuerySingleInfo)")
    sp.add_argument("--single-open-id", required=True)

    sp = sub.add_parser("cancel_single",
                        help="按 SingleOpenId 取消未触发/重呼中的单次发送 (SingleCancel)")
    sp.add_argument("--single-open-id", required=True)

    return p


def main() -> None:
    args = build_parser().parse_args()
    try:
        result = _ACTIONS[args.action](args)
    except BaseException as exc:  # noqa: BLE001
        fail(exc)
        return
    emit(result)


if __name__ == "__main__":
    main()
