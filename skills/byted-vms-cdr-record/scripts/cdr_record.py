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
"""byted-vms-cdr-record · 火山云通信话单 / 录音查询 Skill 脚本.

封装的 TOP Action:
    - QueryCallRecordMsg            query_cdr           按 CallId 精确反查 (V1, form-urlencoded)
    - QueryCallRecordMsgV2          query_cdr_v2        V2 升级接口, JSON body, 支持单次最多 100 条
    - QuerySipRecord                query_sip_record    按被叫/主叫 + 时间窗口列表查话单 (GET /SipRecord/Search)
    - QueryAudioRecordFileUrl       query_record_url    获取录音文件下载 URL
    - QueryAudioRecordToTextFileUrlV2 query_asr_url     获取通话录音 ASR 转文本下载 URL (V2)
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _topclient import call_top, emit, fail  # noqa: E402


def cmd_query_cdr(args: argparse.Namespace) -> Dict[str, Any]:
    """V1: 按 CallId 精确反查话单 (form-urlencoded)."""
    body: Dict[str, Any] = {"CallIdList": args.call_id}
    if args.business_type:
        body["BusinessType"] = args.business_type
    body["Limit"] = args.limit
    body["Offset"] = args.offset
    return call_top("QueryCallRecordMsg", body, form=True)


def cmd_query_sip_record(args: argparse.Namespace) -> Dict[str, Any]:
    """按时间窗 + 被叫/主叫等条件列表查话单.

    GET https://cloud-vms.volcengineapi.com/SipRecord/Search?Action=QuerySipRecord&...
    示例参数:
      Callee=<CalleePhone>&Limit=10&Offset=0
      &BeginCallTimeLowerBound=2026-05-22 00:00:00
      &BeginCallTimeUpperBound=2026-05-28 23:59:59
    """
    params: Dict[str, Any] = {"Limit": args.limit, "Offset": args.offset}
    if args.callee:
        params["Callee"] = args.callee
    if args.caller:
        params["Caller"] = args.caller
    if args.begin_time_lower:
        params["BeginCallTimeLowerBound"] = args.begin_time_lower
    if args.begin_time_upper:
        params["BeginCallTimeUpperBound"] = args.begin_time_upper
    if args.call_id:
        params["CallId"] = args.call_id
    if args.sub_service_type:
        params["SubServiceType"] = args.sub_service_type
    if args.number_pool_no:
        params["NumberPoolNo"] = args.number_pool_no
    if args.call_status:
        params["CallStatus"] = args.call_status
    return call_top("QuerySipRecord", params,
                    method="GET", path="/SipRecord/Search")


def cmd_query_record_url(args: argparse.Namespace) -> Dict[str, Any]:
    body: Dict[str, Any] = {"CallId": args.call_id}
    if args.expire_time is not None:
        body["ExpireTime"] = args.expire_time
    if args.business_type:
        body["BusinessType"] = args.business_type
    resp = call_top("QueryAudioRecordFileUrl", body, form=True)

    # 精简: 把完整双声道 URL 提到顶层 DownloadUrl, 方便用户直接复制下载
    result = (resp or {}).get("Result") or {}
    download_url = result.get("AudioRecordFileUrl") or ""
    expires_at = ""
    if download_url:
        from urllib.parse import urlparse, parse_qs
        try:
            qs = parse_qs(urlparse(download_url).query)
            ts = int(qs.get("x-expires", ["0"])[0])
            if ts:
                import datetime as _dt
                expires_at = _dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, IndexError):
            pass

    summary: Dict[str, Any] = {
        "CallId": args.call_id,
        "DownloadUrl": download_url,
        "ExpiresAt": expires_at,
        "LeftChannelUrl": result.get("AudioRecordLeftFileUrl") or "",
        "RightChannelUrl": result.get("AudioRecordRightFileUrl") or "",
        "Raw": resp,
    }

    if args.save_to and download_url:
        from urllib import request as _req
        save_path = os.path.expanduser(args.save_to)
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        with _req.urlopen(download_url, timeout=60) as r, open(save_path, "wb") as f:
            f.write(r.read())
        summary["SavedTo"] = save_path

    return summary


def cmd_query_cdr_v2(args: argparse.Namespace) -> Dict[str, Any]:
    """V2: 单次最多 100 个 CallId.

    实测 TOP 网关只接受 form-urlencoded + 重复 ``CallIdList`` 字段, JSON body 会
    报 ``Required List parameter 'CallIdList' is not present``. 这里直接用逗号
    分隔的字符串透传给 form 编码层 (与 query_asr_url 处理方式一致).
    """
    call_ids = [c.strip() for c in args.call_id.split(",") if c.strip()]
    body = {"CallIdList": ",".join(call_ids)}
    return call_top("QueryCallRecordMsgV2", body, form=True)


def cmd_query_asr_url(args: argparse.Namespace) -> Dict[str, Any]:
    """V2: 录音 ASR 转文本下载 URL.

    实测 TOP 网关只接受 form-urlencoded + 重复 ``CallIdList`` 字段, JSON body 会
    报 ``Required List parameter 'CallIdList' is not present``. 这里直接用逗号
    分隔的字符串透传给 form 编码层.
    """
    call_ids = [c.strip() for c in args.call_id.split(",") if c.strip()]
    body = {"CallIdList": ",".join(call_ids)}
    resp = call_top("QueryAudioRecordToTextFileUrlV2", body, form=True)

    records = ((resp or {}).get("Result") or {}).get("Records") or []
    summary: Dict[str, Any] = {
        "Records": [
            {
                "CallId": rec.get("CallId"),
                "AsrTextUrl": rec.get("AudioRecordToTextFileUrl") or rec.get("ToTextFileUrl") or "",
            }
            for rec in records
        ],
        "Raw": resp,
    }
    return summary


_ACTIONS = {
    "query_cdr": cmd_query_cdr,
    "query_cdr_v2": cmd_query_cdr_v2,
    "query_sip_record": cmd_query_sip_record,
    "query_record_url": cmd_query_record_url,
    "query_asr_url": cmd_query_asr_url,
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="byted-vms-cdr-record · 火山云通信话单/录音查询")
    sub = p.add_subparsers(dest="action", required=True)

    sp = sub.add_parser("query_cdr",
                        help="按 CallId 精确反查话单 (QueryCallRecordMsg, V1)")
    sp.add_argument("--call-id", required=True,
                    help="平台分配的呼叫流水号; 仅由异步话单回调或业务侧持久化提供")
    sp.add_argument("--business-type", help="如 voiceNotify / privacyNumber / aicall")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--offset", type=int, default=0)

    sp = sub.add_parser("query_sip_record",
                        help="按被叫/主叫 + 时间窗口列表查话单 (QuerySipRecord)")
    sp.add_argument("--callee", help="被叫号码")
    sp.add_argument("--caller", help="主叫号码")
    sp.add_argument("--begin-time-lower",
                    help="呼叫开始时间下界, 格式 'YYYY-MM-DD HH:MM:SS'")
    sp.add_argument("--begin-time-upper",
                    help="呼叫开始时间上界, 格式 'YYYY-MM-DD HH:MM:SS'")
    sp.add_argument("--call-id", help="可选: 按 CallId 过滤")
    sp.add_argument("--sub-service-type",
                    help="子业务类型: 101 SIP / 102 语音通知 / 103 双呼 / 104 智能外呼 / "
                         "201~206 隐私号 (AXB/AXN/AXNE/AXYB/PAXYB/AXG); "
                         "见 references/vms-fundamentals.md §1")
    sp.add_argument("--number-pool-no", help="号码池编号")
    sp.add_argument("--call-status",
                    help="呼叫状态过滤, 如 ANSWERED/NOANSWER/BUSY/FAILED")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--offset", type=int, default=0)

    sp = sub.add_parser("query_record_url", help="获取录音 URL (QueryAudioRecordFileUrl)")
    sp.add_argument("--call-id", required=True)
    sp.add_argument("--business-type", help="同上")
    sp.add_argument("--expire-time", type=int, help="URL 过期秒数, 默认平台值")
    sp.add_argument("--save-to",
                    help="可选: 把录音文件直接保存到本地路径, 如 ~/Downloads/x.wav")

    sp = sub.add_parser("query_cdr_v2",
                        help="V2 按 CallId 批量查话单 (QueryCallRecordMsgV2, JSON, ≤100)")
    sp.add_argument("--call-id", required=True,
                    help="逗号分隔的 CallId 列表, 单次最多 100 个")

    sp = sub.add_parser("query_asr_url",
                        help="录音 ASR 转文本下载 URL (QueryAudioRecordToTextFileUrlV2, ≤100)")
    sp.add_argument("--call-id", required=True,
                    help="逗号分隔的 CallId 列表, 单次最多 100 个")

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
