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
"""byted-vms-configure · 火山云通信通用配置 Skill 脚本.

通用能力层: 仅负责跨业务的「号码可呼性 / 风控 / 主叫鉴权」类校验.

注意:
- 所有 TTS 模板相关操作 (创建 / 更新 / 删除 / 查询) 由 byted-vms-voice-notify skill 提供.
- 所有「录音文件 / 通用资源 (list_resource / list_usable / update_resource /
  delete_resource / get_upload_url / submit_upload / create_voice /
  query_voice / delete_voice)」也已迁移到 byted-vms-voice-notify skill, 本 skill 不再
  封装上述任何入口.

封装的 TOP Action:
    跨业务通用查询 / 校验:
    - QueryRiskDenyInfo      query_risk_deny     号码是否在平台风控黑名单
    - QueryCanCall           query_can_call      号码当前是否可被呼叫 (综合状态)
    - QueryAuth              query_auth          主叫鉴权状态 (Click2Call 必填鉴权)

仅依赖同目录下 _topclient.py, 不跨 skill 包 import.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import uuid
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _topclient import call_top, emit, fail  # noqa: E402


# ---------- 通用查询 / 校验 (跨业务) ----------

def cmd_query_risk_deny(args: argparse.Namespace) -> Dict[str, Any]:
    """查号码是否在平台风控黑名单 (QueryRiskDenyInfo, JSON body).

    官方文档: https://www.volcengine.com/docs/6358/2196026
    必填: Mobile, EncryptType, AccountRequestId.
        EncryptType=1 → Mobile 为 MD5 (32 位小写 hex)
        EncryptType=2 → Mobile 为明文
    若用户传 EncryptType=1 但 Mobile 仍是明文手机号, 这里自动做一次小写 MD5.
    AccountRequestId 缺省自动生成 UUID, 便于排查.
    """
    mobile = args.mobile
    encrypt_type = args.encrypt_type if args.encrypt_type is not None else 2
    if encrypt_type == 1 and not re.fullmatch(r"[0-9a-f]{32}", mobile or ""):
        mobile = hashlib.md5(mobile.encode("utf-8")).hexdigest()
    account_request_id = args.account_request_id or uuid.uuid4().hex
    body: Dict[str, Any] = {
        "Mobile": mobile,
        "EncryptType": encrypt_type,
        "AccountRequestId": account_request_id,
    }
    return call_top("QueryRiskDenyInfo", body)


def cmd_query_can_call(args: argparse.Namespace) -> Dict[str, Any]:
    """查号码是否可被呼叫 (QueryCanCall, form-urlencoded).

    SDK 走 Utils.mapToPairList(paramsToMap(RiskControlReq)), 保留 Java
    小写驼峰字段名: customerNumberList / businessLineId / callType.
    customerNumberList 在服务端是 List, 必须用重复键 a=1&a=2 形式编码,
    所以这里把逗号分隔的 --numbers 拆成 list.
    """
    numbers = [n.strip() for n in args.numbers.split(",") if n.strip()]
    body: Dict[str, Any] = {"customerNumberList": numbers}
    if args.business_line_id is not None:
        body["businessLineId"] = args.business_line_id
    if args.call_type is not None:
        body["callType"] = args.call_type
    return call_top("QueryCanCall", body, form=True)


def cmd_query_auth(args: argparse.Namespace) -> Dict[str, Any]:
    """查主叫鉴权状态 (QueryAuth, form-urlencoded). Click2Call 主叫需先鉴权.

    SDK 字段名为小写驼峰 phone, 实测大写 Phone 也接受 (返回 aes decode 路径相同).
    """
    return call_top("QueryAuth", {"phone": args.phone}, form=True)


_ACTIONS = {
    "query_risk_deny": cmd_query_risk_deny,
    "query_can_call": cmd_query_can_call,
    "query_auth": cmd_query_auth,
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="byted-vms-configure · 火山云通信 跨业务通用查询/校验 "
                    "(录音/资源/TTS 全部已迁移至 byted-vms-voice-notify)"
    )
    sub = p.add_subparsers(dest="action", required=True)

    sp = sub.add_parser("query_risk_deny",
                        help="查号码是否在平台风控黑名单 (QueryRiskDenyInfo)")
    sp.add_argument("--mobile", required=True,
                    help="目标号码; EncryptType=2 传明文, EncryptType=1 传 MD5 32 位小写 hex (传明文将自动 MD5)")
    sp.add_argument("--account-request-id",
                    help="客户请求 ID, 缺省自动生成 UUID")
    sp.add_argument("--encrypt-type", type=int, choices=[1, 2],
                    help="加密类型: 1=MD5, 2=明文 (默认 2)")

    sp = sub.add_parser("query_can_call",
                        help="查号码是否可被呼叫综合状态 (QueryCanCall)")
    sp.add_argument("--numbers", required=True,
                    help="客户号码列表, 逗号分隔, 例如 13800138000,13900139000")
    sp.add_argument("--business-line-id", type=int,
                    help="业务线 (1=语音通知 2=智能外呼 3=隐私号 4=Click2Call)")
    sp.add_argument("--call-type", type=int,
                    help="呼叫方向 (1=主叫 2=被叫)")

    sp = sub.add_parser("query_auth",
                        help="查主叫鉴权状态 (QueryAuth, Click2Call 必填)")
    sp.add_argument("--phone", required=True, help="主叫号码 (AES 加密后传入)")

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
