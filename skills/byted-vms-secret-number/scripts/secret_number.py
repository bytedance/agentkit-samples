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
"""byted-vms-secret-number · 火山云通信隐私号 Skill 脚本.

封装的 TOP Action:
    - BindAXB                  bind_axb
    - SelectNumberAndBindAXB   select_and_bind_axb
    - BindAXN                  bind_axn
    - SelectNumberAndBindAXN   select_and_bind_axn   平台选号 + AXN 绑定
    - BindAXNE                 bind_axne
    - UnbindAXB                unbind_axb            (form-urlencoded, NumberPoolNo+SubId)
    - UnbindAXN                unbind_axn
    - UnbindAXNE               unbind_axne
    - QuerySubscription        query_subscription    按 SubId 单条查询
    - QuerySubscriptionForList query_subscription_list  按号码池/号码批量查询
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _topclient import call_top, emit, fail  # noqa: E402

DEFAULT_EXPIRE_SECS = 30 * 24 * 60 * 60  # 30 天
# TOP 的 ExpireTime 字段语义是"绝对秒级 unix 时间戳", 且必须 >= now+60s.
# 用户传入若是相对秒数 (< 该阈值, 例如 2592000 表示 30 天), skill 自动加上当前
# 时间戳转成绝对值; 若用户已经传绝对时间戳 (>= 阈值, 大约 2001-09-09 之后) 则原样
# 透传, 兼容老用法.
_RELATIVE_EXPIRE_THRESHOLD = 10 ** 9


def _resolve_expire_time(value: int) -> int:
    """把 ExpireTime 统一成绝对秒级 unix 时间戳."""
    if value < _RELATIVE_EXPIRE_THRESHOLD:
        return int(time.time()) + value
    return value


def _attach_common(body: Dict[str, Any], args: argparse.Namespace) -> None:
    # ExpireTime 一定下发 (走默认值或用户值), 避免 TOP 端使用默认值时再次踩到
    # "ExpireTime must be 1 minute later" 的旧坑.
    body["ExpireTime"] = _resolve_expire_time(args.expire_time or DEFAULT_EXPIRE_SECS)
    if args.ext:
        body["Ext"] = args.ext
    if args.user_data:
        body["UserData"] = args.user_data
    if args.record_flag is not None:
        body["RecordFlag"] = args.record_flag
    if args.asr_flag is not None:
        body["AsrFlag"] = args.asr_flag


def cmd_bind_axb(args: argparse.Namespace) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "PhoneNoA": args.phone_a,
        "PhoneNoB": args.phone_b,
        "PhoneNoX": args.phone_x,
        "NumberPoolNo": args.number_pool_no,
    }
    _attach_common(body, args)
    return call_top("BindAXB", body)


def cmd_select_and_bind_axb(args: argparse.Namespace) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "PhoneNoA": args.phone_a,
        "PhoneNoB": args.phone_b,
        "NumberPoolNo": args.number_pool_no,
    }
    if args.city_code:
        body["CityCode"] = args.city_code
    _attach_common(body, args)
    return call_top("SelectNumberAndBindAXB", body)


def cmd_bind_axn(args: argparse.Namespace) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "PhoneNoA": args.phone_a,
        "PhoneNoX": args.phone_x,
        "NumberPoolNo": args.number_pool_no,
    }
    _attach_common(body, args)
    return call_top("BindAXN", body)


def cmd_bind_axne(args: argparse.Namespace) -> Dict[str, Any]:
    # 注意: BindAXNE 接口的分机号字段名是 `PhoneNoE`, 不是 `Extension`.
    # 参考: https://www.volcengine.com/docs/6358/172909?lang=zh
    body: Dict[str, Any] = {
        "PhoneNoA": args.phone_a,
        "PhoneNoX": args.phone_x,
        "PhoneNoB": args.phone_b,
        "PhoneNoE": args.extension,
        "NumberPoolNo": args.number_pool_no,
    }
    _attach_common(body, args)
    return call_top("BindAXNE", body)


def cmd_unbind_axb(args: argparse.Namespace) -> Dict[str, Any]:
    body: Dict[str, Any] = {"SubId": args.sub_id, "NumberPoolNo": args.number_pool_no}
    return call_top("UnbindAXB", body, form=True)


def cmd_unbind_axn(args: argparse.Namespace) -> Dict[str, Any]:
    body: Dict[str, Any] = {"SubId": args.sub_id, "NumberPoolNo": args.number_pool_no}
    return call_top("UnbindAXN", body, form=True)


def cmd_unbind_axne(args: argparse.Namespace) -> Dict[str, Any]:
    body: Dict[str, Any] = {"SubId": args.sub_id, "NumberPoolNo": args.number_pool_no}
    return call_top("UnbindAXNE", body, form=True)


def cmd_select_and_bind_axn(args: argparse.Namespace) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "PhoneNoA": args.phone_a,
        "NumberPoolNo": args.number_pool_no,
    }
    if args.phone_b:
        body["PhoneNoB"] = args.phone_b
    body["ExpireTime"] = _resolve_expire_time(args.expire_time or DEFAULT_EXPIRE_SECS)
    if args.audio_record_flag is not None:
        body["AudioRecordFlag"] = args.audio_record_flag
    if args.city_code:
        body["CityCode"] = args.city_code
    if args.city_code_by_phone_no:
        body["CityCodeByPhoneNo"] = args.city_code_by_phone_no
    if args.degrade_city_list:
        body["DegradeCityList"] = json.loads(args.degrade_city_list)
    if args.random_flag is not None:
        body["RandomFlag"] = args.random_flag
    if args.user_data:
        body["UserData"] = args.user_data
    return call_top("SelectNumberAndBindAXN", body, form=True)


def cmd_query_subscription(args: argparse.Namespace) -> Dict[str, Any]:
    if not args.sub_id:
        raise ValueError("--sub-id 必填 (SubId 由 bind 接口返回)")
    body: Dict[str, Any] = {"SubId": args.sub_id}
    if args.number_pool_no:
        body["NumberPoolNo"] = args.number_pool_no
    return call_top("QuerySubscription", body)


def cmd_query_subscription_list(args: argparse.Namespace) -> Dict[str, Any]:
    """按号码池 + (可选) PhoneNoA / PhoneNoX 等条件批量查绑定关系.

    设计约束: 不在 byted-vms-secret-number 内部反查号码池. 用户只给 X 号时,
    Agent 应先调度 byted-vms-number-pool 的 `query_number --phone <X>` 取得
    NumberPoolNo, 再回到本 skill 调用 query_subscription_list. 这是
    skills-lite 「skill 之间不互相 import / 不跨域调原子能力」的硬性边界.
    """
    body: Dict[str, Any] = {
        "NumberPoolNo": args.number_pool_no,
        "Limit": args.limit,
        "Offset": args.offset,
    }
    if args.phone_a:
        body["PhoneNoA"] = args.phone_a
    if args.phone_b:
        body["PhoneNoB"] = args.phone_b
    if args.phone_x:
        body["PhoneNoX"] = args.phone_x
    if args.sub_type:
        body["SubType"] = args.sub_type
    return call_top("QuerySubscriptionForList", body)


_ACTIONS = {
    "bind_axb": cmd_bind_axb,
    "select_and_bind_axb": cmd_select_and_bind_axb,
    "bind_axn": cmd_bind_axn,
    "select_and_bind_axn": cmd_select_and_bind_axn,
    "bind_axne": cmd_bind_axne,
    "unbind_axb": cmd_unbind_axb,
    "unbind_axn": cmd_unbind_axn,
    "unbind_axne": cmd_unbind_axne,
    "query_subscription": cmd_query_subscription,
    "query_subscription_list": cmd_query_subscription_list,
}


def _add_common(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--expire-time", type=int,
                    default=DEFAULT_EXPIRE_SECS,
                    help=("绑定过期时间. 接受两种写法: "
                          "(1) 相对秒数 (< 1e9), 例如 2592000 表示 30 天后过期, "
                          "skill 会自动叠加当前时间戳; "
                          "(2) 绝对秒级 unix 时间戳 (>= 1e9), 直接透传. "
                          f"默认 30 天 ({DEFAULT_EXPIRE_SECS} 秒). "
                          "TOP 要求最终值至少比当前时间晚 60 秒."))
    sp.add_argument("--ext")
    sp.add_argument("--user-data")
    sp.add_argument("--record-flag", type=int, choices=[0, 1], help="0关 1开")
    sp.add_argument("--asr-flag", type=int, choices=[0, 1], help="0关 1开")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="byted-vms-secret-number · 火山云通信隐私号")
    sub = p.add_subparsers(dest="action", required=True)

    sp = sub.add_parser("bind_axb", help="AXB 绑定 (BindAXB), X 由用户指定")
    sp.add_argument("--phone-a", required=True)
    sp.add_argument("--phone-b", required=True)
    sp.add_argument("--phone-x", required=True, help="平台已分配给客户的 X 号码")
    sp.add_argument("--number-pool-no", required=True)
    _add_common(sp)

    sp = sub.add_parser("select_and_bind_axb",
                        help="平台选号并 AXB 绑定 (SelectNumberAndBindAXB)")
    sp.add_argument("--phone-a", required=True)
    sp.add_argument("--phone-b", required=True)
    sp.add_argument("--number-pool-no", required=True)
    sp.add_argument("--city-code", help="城市码, 同城显示")
    _add_common(sp)

    sp = sub.add_parser("bind_axn", help="AXN 绑定 (BindAXN)")
    sp.add_argument("--phone-a", required=True)
    sp.add_argument("--phone-x", required=True)
    sp.add_argument("--number-pool-no", required=True)
    _add_common(sp)

    sp = sub.add_parser("select_and_bind_axn",
                        help="平台选号 + AXN 绑定 (SelectNumberAndBindAXN)")
    sp.add_argument("--phone-a", required=True, help="A 号码")
    sp.add_argument("--phone-b", help="B 号码, 不传则平台占位")
    sp.add_argument("--number-pool-no", required=True)
    sp.add_argument("--expire-time", type=int,
                    default=DEFAULT_EXPIRE_SECS,
                    help=("绑定过期时间. 接受相对秒数 (< 1e9, 默认 30 天) "
                          "或绝对秒级时间戳; 相对秒数会自动叠加当前时间."))
    sp.add_argument("--audio-record-flag", type=int, choices=[0, 1],
                    help="0关 1开 (默认开启)")
    sp.add_argument("--city-code", help="选号指定城市")
    sp.add_argument("--city-code-by-phone-no", choices=["A", "B"],
                    help="按 A 或 B 号码所在城市选号")
    sp.add_argument("--degrade-city-list",
                    help="JSON 数组, 降级城市列表; 支持 'PNPC' 表示省会")
    sp.add_argument("--random-flag", type=int, choices=[0, 1],
                    help="是否随机选号 0关(默认) 1开")
    sp.add_argument("--user-data", help="最大 2048")

    sp = sub.add_parser("bind_axne", help="AXNE 绑定 (BindAXNE)")
    sp.add_argument("--phone-a", required=True)
    sp.add_argument("--phone-x", required=True)
    sp.add_argument("--phone-b", required=True)
    sp.add_argument("--extension", required=True, help="分机号")
    sp.add_argument("--number-pool-no", required=True)
    _add_common(sp)

    sp = sub.add_parser("unbind_axb", help="AXB 解绑 (UnbindAXB)")
    sp.add_argument("--sub-id", required=True, help="绑定关系 ID, 由 bind 接口返回")
    sp.add_argument("--number-pool-no", required=True)

    sp = sub.add_parser("unbind_axn", help="AXN 解绑 (UnbindAXN)")
    sp.add_argument("--sub-id", required=True)
    sp.add_argument("--number-pool-no", required=True)

    sp = sub.add_parser("unbind_axne", help="AXNE 解绑 (UnbindAXNE)")
    sp.add_argument("--sub-id", required=True)
    sp.add_argument("--number-pool-no", required=True)

    sp = sub.add_parser("query_subscription", help="按 SubId 查绑定关系 (QuerySubscription)")
    sp.add_argument("--sub-id", required=True, help="绑定关系 ID, 由 bind 接口返回")
    sp.add_argument("--number-pool-no")

    sp = sub.add_parser("query_subscription_list",
                        help="按号码池/号码批量查绑定关系 (QuerySubscriptionForList)")
    sp.add_argument("--number-pool-no", required=True,
                    help="号码池号; 仅给 X 号时, 请先调用 byted-vms-number-pool 的 "
                         "query_number --phone <X> 取池号")
    sp.add_argument("--phone-a")
    sp.add_argument("--phone-b")
    sp.add_argument("--phone-x")
    sp.add_argument("--sub-type",
                    help="绑定关系类型, 如 AXB / AXN / AXNE")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--offset", type=int, default=0)

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
