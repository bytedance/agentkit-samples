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
"""byted-vms-number-pool · 火山云通信号码池/号码/资质 Skill 脚本.

封装的 TOP Action:
    - NumberPoolList            list_pool             查询号码池 (form-urlencoded)
    - CreateNumberPool          create_pool
    - UpdateNumberPoolV2        update_pool           更新号码池 (改名/备注/资质)
    - NumberList                list_number           查询号码池下号码
    - EnableOrDisableNumber     toggle_number         启用/停用号码
    - AddQualification          add_qualification     提交资质
    - QueryQualification        query_qualification   按 ID/状态/名称查资质 (单条精查)
    - QueryQualificationList    list_qualification    查询资质列表 (form-urlencoded)
    - UpdateQualification       update_qualification
    - UploadQualificationFileV2 upload_qualification_file 资质材料上传
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _topclient import call_top, emit, fail  # noqa: E402


def cmd_list_pool(args: argparse.Namespace) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "SubServiceType": args.sub_service_type,
        "Limit": args.limit,
        "Offset": args.offset,
    }
    if args.name:
        body["Name"] = args.name
    if args.number_pool_no:
        body["NumberPoolNo"] = args.number_pool_no
    return call_top("NumberPoolList", body, form=True)


def cmd_create_pool(args: argparse.Namespace) -> Dict[str, Any]:
    # ServiceType 枚举 (实测): 100=普通号码 / 200=隐私号 / ...
    # SubServiceType 见 references/vms-fundamentals.md §1:
    #   普通语音 100 系列: 101 SIP / 102 语音通知 / 103 双呼 / 104 智能外呼 / 105~108
    #   隐私号 200 系列:   201 AXB / 202 AXN / 203 AXNE / 204 AXYB / 205 PAXYB / 206 AXG
    sub2svc = {
        101: 100, 102: 100, 103: 100, 104: 100,
        105: 100, 106: 100, 107: 100, 108: 100,
        201: 200, 202: 200, 203: 200, 204: 200, 205: 200, 206: 200,
    }
    service_type = args.service_type
    if service_type is None:
        service_type = sub2svc.get(args.sub_service_type)
    body: Dict[str, Any] = {
        "Name": args.name,
        "SubServiceType": args.sub_service_type,
    }
    if service_type is not None:
        body["ServiceType"] = service_type
    if args.qualification_id:
        body["QualificationId"] = args.qualification_id
    if args.remark:
        body["Remark"] = args.remark
    if args.choose_pretty is not None:
        body["ChoosePretty"] = args.choose_pretty
    return call_top("CreateNumberPool", body)


def cmd_update_pool(args: argparse.Namespace) -> Dict[str, Any]:
    """更新号码池 (UpdateNumberPoolV2). 通常用于改名/改备注/换资质."""
    body: Dict[str, Any] = {"NumberPoolNo": args.number_pool_no}
    if args.name is not None:
        body["Name"] = args.name
    if args.remark is not None:
        body["Remark"] = args.remark
    if args.qualification_id is not None:
        body["QualificationId"] = args.qualification_id
    return call_top("UpdateNumberPoolV2", body)


def cmd_list_number(args: argparse.Namespace) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "NumberPoolNo": args.number_pool_no,
        "Limit": args.limit,
        "Offset": args.offset,
    }
    if args.phone:
        body["Phone"] = args.phone
    if args.status is not None:
        body["Status"] = args.status
    return call_top("NumberList", body)


def _extract_list(payload: Any, *keys: str) -> list:
    """从 TOP 响应里提取列表字段, 兼容 NumberPoolList / NumberList / List / Records / Items."""
    if not isinstance(payload, dict):
        return []
    for key in keys:
        val = payload.get(key)
        if isinstance(val, list):
            return val
    for key in ("List", "Records", "Items"):
        val = payload.get(key)
        if isinstance(val, list):
            return val
    return []


# 通用语音 100 系列 + 隐私号 200 系列, 见 references/vms-fundamentals.md §1
_DEFAULT_SCAN_SUB_TYPES = (101, 102, 103, 104, 105, 106, 107, 108,
                           201, 202, 203, 204, 205, 206)


def cmd_query_number(args: argparse.Namespace) -> Dict[str, Any]:
    """按手机号反查所属号码池 + 号码详情.

    实现: 遍历指定 (或默认) 的 SubServiceType, 调用 NumberPoolList 拉号码池,
    再在每个池里用 NumberList(Phone=...) 命中即返回. 用于业务层 skill (如
    byted-vms-secret-number) 在只拿到号码时先取 NumberPoolNo, 然后再调本业务的
    QuerySubscriptionForList / Unbind* 等接口.

    返回: { Phone, NumberPoolNo, SubServiceType, Pool, Number }; 未找到时
    返回 { ok: false, errorCode: "NUMBER_NOT_FOUND", scanned: [...] }.
    """
    if args.sub_service_type is not None:
        scan = (args.sub_service_type,)
    else:
        scan = _DEFAULT_SCAN_SUB_TYPES

    page = 100
    for sub_type in scan:
        offset = 0
        while True:
            pool_resp = call_top("NumberPoolList", {
                "SubServiceType": sub_type,
                "Limit": page,
                "Offset": offset,
            }, form=True)
            pool_result = (pool_resp or {}).get("Result") or pool_resp or {}
            pools = _extract_list(pool_result, "NumberPoolList", "NumberPools")
            if not pools:
                break
            for pool in pools:
                pool_no = (pool.get("NumberPoolNo") or pool.get("Id")
                           or pool.get("NumberPoolId"))
                if not pool_no:
                    continue
                num_resp = call_top("NumberList", {
                    "NumberPoolNo": pool_no,
                    "Phone": args.phone,
                    "Limit": 1,
                    "Offset": 0,
                })
                num_result = (num_resp or {}).get("Result") or num_resp or {}
                numbers = _extract_list(num_result, "NumberList", "Numbers")
                if numbers:
                    return {
                        "ok": True,
                        "Phone": args.phone,
                        "NumberPoolNo": pool_no,
                        "SubServiceType": sub_type,
                        "Pool": pool,
                        "Number": numbers[0],
                    }
            if len(pools) < page:
                break
            offset += page
    return {
        "ok": False,
        "errorCode": "NUMBER_NOT_FOUND",
        "message": f"未在指定 SubServiceType 范围内找到号码 {args.phone} 所属号码池.",
        "scanned": list(scan),
        "Phone": args.phone,
    }


def cmd_toggle_number(args: argparse.Namespace) -> Dict[str, Any]:
    """启用 / 停用号码池中的号码 (EnableOrDisableNumber).

    服务端 (官方文档 + 实测) 期望:
      - NumberList: String[] 号码数组, 单批最多 100 个
      - EnableCode: 1=启用 / 2=停用 (注意: 不是 0/1 boolean)
    之前传 ``Enable: bool`` 会报 "enable code cannot be null"; 传 ``PhoneList``
    或单字段 ``Number`` / ``Id`` 会报 "id和number至少一个不为null".
    """
    phones = [p.strip() for p in args.phone_list.split(",") if p.strip()]
    if not phones:
        return {
            "ok": False,
            "errorCode": "RequestParametersError",
            "message": "--phone-list 不能为空",
            "requestId": None,
        }
    return call_top("EnableOrDisableNumber", {
        "NumberPoolNo": args.number_pool_no,
        "NumberList": phones,
        "EnableCode": 1 if args.enable else 2,
    })


def cmd_add_qualification(args: argparse.Namespace) -> Dict[str, Any]:
    body: Dict[str, Any] = {}
    if args.payload:
        body.update(json.loads(args.payload))
    if args.name:
        body["Name"] = args.name
    if args.qualification_type is not None:
        body["QualificationType"] = args.qualification_type
    if args.industry_type is not None:
        body["IndustryType"] = args.industry_type
    if args.business_type is not None:
        body["BusinessType"] = args.business_type
    return call_top("AddQualification", body)


def cmd_query_qualification(args: argparse.Namespace) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "Limit": args.limit,
        "Offset": args.offset,
    }
    if args.qualification_id:
        body["QualificationId"] = args.qualification_id
    if args.status is not None:
        body["Status"] = args.status
    if args.name:
        body["Name"] = args.name
    return call_top("QueryQualification", body)


def cmd_list_qualification(args: argparse.Namespace) -> Dict[str, Any]:
    """查询资质列表 (QueryQualification, JSON body).

    参考 https://www.volcengine.com/docs/6358/173331?lang=zh
    实测平台没有 QueryQualificationList, 列表查询直接走 QueryQualification + JSON body.
    返回 Result.Records[], 每条 Record 含 QualificationMainInfoVO/AdminInfoVO/ScenarioInfoVOList.
    """
    body: Dict[str, Any] = {
        "Limit": args.limit,
        "Offset": args.offset,
    }
    if args.name:
        body["Name"] = args.name
    if args.status is not None:
        body["ApprovalStatus"] = args.status
    if args.qualification_type is not None:
        body["QualificationType"] = args.qualification_type
    if args.business_type is not None:
        body["BusinessType"] = args.business_type
    if args.industry_type is not None:
        body["IndustryType"] = args.industry_type
    resp = call_top("QueryQualification", body)
    result = (resp or {}).get("Result") or {}
    records = result.get("Records") or result.get("List") or []
    items = []
    for rec in records:
        main = rec.get("QualificationMainInfoVO") or {}
        admin = rec.get("QualificationAdminInfoVO") or {}
        items.append({
            "QualificationId": main.get("QualificationId") or admin.get("QualificationId"),
            "QualificationNo": main.get("QualificationNo"),
            "Entity": main.get("QualificationEntity"),
            "ShortName": main.get("EnterpriseShortName"),
            "ApprovalStatus": main.get("ApprovalStatus"),
            "ApprovalStatusText": {
                0: "待审核", 1: "通过", 2: "驳回",
            }.get(main.get("ApprovalStatus"), str(main.get("ApprovalStatus"))),
            "ApprovalDoneReason": main.get("ApprovalDoneReason"),
            "AdminName": admin.get("Name"),
            "AdminPhone": admin.get("ContactNumber"),
            "UnitSocialCreditCode": main.get("UnitSocialCreditCode"),
        })
    summary = {
        "Total": result.get("Total") or result.get("TotalCount") or len(items),
        "Items": items,
        "Raw": resp,
    }
    return summary


def cmd_update_qualification(args: argparse.Namespace) -> Dict[str, Any]:
    body: Dict[str, Any] = {"QualificationId": args.qualification_id}
    if args.payload:
        body.update(json.loads(args.payload))
    return call_top("UpdateQualification", body)


def cmd_upload_qualification_file(args: argparse.Namespace) -> Dict[str, Any]:
    """上传资质材料 (UploadQualificationFileV2).

    入参 FileUrl 必须为公网可访问的图片/PDF URL. FileType 一般跟随资质类型
    (营业执照/法人身份证正反面/经办人身份证正反面 等), 由用户业务侧约定枚举.
    """
    body: Dict[str, Any] = {"FileUrl": args.file_url}
    if args.qualification_id:
        body["QualificationId"] = args.qualification_id
    if args.file_type is not None:
        body["FileType"] = args.file_type
    if args.file_name:
        body["FileName"] = args.file_name
    return call_top("UploadQualificationFileV2", body)


def cmd_apply_number(args: argparse.Namespace) -> Dict[str, Any]:
    """申请号码 (购号).

    实测火山 VMS TOP 网关未暴露「号码申请」/「购买号码」的 OpenAPI Action
    (尝试 ApplyNumber / BuyNumber / CreateNumberApplyRecord / SubmitNumberApply
    等 20+ 候选名均报 Could not find operation), 写入操作仅在控制台开放, 需
    人工提交申请单并经平台审核.

    本命令不发起任何网络请求, 直接返回引导信息, 让用户去控制台手工申请.
    """
    return {
        "ok": False,
        "errorCode": "ApiNotSupported",
        "message": "VMS 平台未开放「申请号码 / 购号」OpenAPI 接口, 请在控制台手工申请.",
        "action": "请前往 https://console.volcengine.com/cloud_vms/number "
                  "页面点击「申请号码」操作.",
        "console": "https://console.volcengine.com/cloud_vms/number",
        "context": {
            "NumberPoolNo": args.number_pool_no,
            "Count": args.count,
            "QualificationId": args.qualification_id,
        },
        "next": [
            "1. 进入号码池 -> 选中目标号码池 -> 点击「申请号码」.",
            "2. 选择关联资质 + 业务类型 + 申请数量 + 归属地 + 使用时长, 提交审核.",
            "3. 审核通过后, 用 list_number --number-pool-no <池号> 即可看到入池号码.",
            "4. 申请记录可用 query_apply_record 查询审核状态.",
        ],
    }


def cmd_query_apply_record(args: argparse.Namespace) -> Dict[str, Any]:
    """查询号码申请记录 (QueryNumberApplyRecordList, JSON body)."""
    body: Dict[str, Any] = {
        "Limit": args.limit,
        "Offset": args.offset,
    }
    if args.number_pool_no:
        body["NumberPoolNo"] = args.number_pool_no
    if args.sub_service_type is not None:
        body["SubServiceType"] = args.sub_service_type
    if args.apply_status is not None:
        body["ApplyStatusCode"] = args.apply_status
    return call_top("QueryNumberApplyRecordList", body)


_ACTIONS = {
    "list_pool": cmd_list_pool,
    "create_pool": cmd_create_pool,
    "update_pool": cmd_update_pool,
    "list_number": cmd_list_number,
    "query_number": cmd_query_number,
    "apply_number": cmd_apply_number,
    "query_apply_record": cmd_query_apply_record,
    "toggle_number": cmd_toggle_number,
    "add_qualification": cmd_add_qualification,
    "query_qualification": cmd_query_qualification,
    "list_qualification": cmd_list_qualification,
    "update_qualification": cmd_update_qualification,
    "upload_qualification_file": cmd_upload_qualification_file,
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="byted-vms-number-pool · 号码池/号码/资质")
    sub = p.add_subparsers(dest="action", required=True)

    sp = sub.add_parser("list_pool", help="查询号码池 (NumberPoolList)")
    sp.add_argument("--sub-service-type", type=int, default=102,
                    help="见 references/vms-fundamentals.md §1: "
                         "101 SIP / 102 语音通知 / 103 双呼 / 104 智能外呼 / "
                         "201 AXB / 202 AXN / 203 AXNE / 204 AXYB / 205 PAXYB / 206 AXG")
    sp.add_argument("--name")
    sp.add_argument("--number-pool-no")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--offset", type=int, default=0)

    sp = sub.add_parser("create_pool", help="创建号码池 (CreateNumberPool)")
    sp.add_argument("--name", required=True)
    sp.add_argument("--sub-service-type", type=int, required=True,
                    help="101/102/103/104 (普通语音) 或 201~206 (隐私号), "
                         "详见 references/vms-fundamentals.md §1")
    sp.add_argument("--service-type", type=int,
                    help="100=普通号码 200=隐私号; 不传则按 sub-service-type 自动推导")
    sp.add_argument("--qualification-id", help="挂载的资质 ID")
    sp.add_argument("--remark")
    sp.add_argument("--choose-pretty", type=lambda x: x.lower() == "true",
                    help="是否靓号池 true/false")

    sp = sub.add_parser("update_pool", help="更新号码池 (UpdateNumberPoolV2)")
    sp.add_argument("--number-pool-no", required=True)
    sp.add_argument("--name", help="新名称")
    sp.add_argument("--remark", help="新备注")
    sp.add_argument("--qualification-id", help="新资质 ID")

    sp = sub.add_parser("list_number", help="查询号码池下号码 (NumberList)")
    sp.add_argument("--number-pool-no", required=True)
    sp.add_argument("--phone")
    sp.add_argument("--status", type=int, help="0停用 1启用")
    sp.add_argument("--limit", type=int, default=50)
    sp.add_argument("--offset", type=int, default=0)

    sp = sub.add_parser("query_number",
                        help="按手机号反查所属号码池 (遍历 NumberPoolList + NumberList)")
    sp.add_argument("--phone", required=True, help="要反查的号码")
    sp.add_argument("--sub-service-type", type=int,
                    help="限定 SubServiceType (101~108 普通语音 / 201~206 隐私号); "
                         "不传则按默认顺序遍历全部, 见 references/vms-fundamentals.md §1")

    sp = sub.add_parser("toggle_number", help="启用/停用号码 (EnableOrDisableNumber)")
    sp.add_argument("--number-pool-no", required=True)
    sp.add_argument("--phone-list", required=True, help="逗号分隔")
    sp.add_argument("--enable", type=lambda x: x.lower() == "true", required=True,
                    help="true=启用 false=停用")

    sp = sub.add_parser("apply_number",
                        help="申请号码 (购号; 平台未开放 API, 仅返回控制台引导)")
    sp.add_argument("--number-pool-no", help="目标号码池编号 (展示用)")
    sp.add_argument("--count", type=int, default=1, help="申请数量 (展示用)")
    sp.add_argument("--qualification-id", help="关联资质 ID (展示用)")

    sp = sub.add_parser("query_apply_record",
                        help="查询号码申请记录 (QueryNumberApplyRecordList)")
    sp.add_argument("--number-pool-no")
    sp.add_argument("--sub-service-type", type=int,
                    help="101/102/103/104/201~206, 见 references/vms-fundamentals.md §1")
    sp.add_argument("--apply-status", type=int,
                    help="申请状态码: 1待审核 2审核中 7审核通过 8审核失败 等")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--offset", type=int, default=0)

    sp = sub.add_parser("add_qualification", help="提交资质 (AddQualification)")
    sp.add_argument("--name")
    sp.add_argument("--qualification-type", type=int, help="0企业 1个体")
    sp.add_argument("--industry-type", type=int)
    sp.add_argument("--business-type", type=int)
    sp.add_argument("--payload", help="完整 JSON, 覆盖以上字段")

    sp = sub.add_parser("query_qualification", help="查询资质 (QueryQualification)")
    sp.add_argument("--qualification-id")
    sp.add_argument("--status", type=int, help="0待审核 1通过 2驳回")
    sp.add_argument("--name")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--offset", type=int, default=0)

    sp = sub.add_parser("list_qualification",
                        help="查询资质列表 (QueryQualificationList, "
                             "doc=173331, form-urlencoded)")
    sp.add_argument("--name", help="主体名称, 模糊匹配")
    sp.add_argument("--status", type=int, help="0待审核 1通过 2驳回")
    sp.add_argument("--qualification-type", type=int, help="0企业 1个体")
    sp.add_argument("--business-type", type=int,
                    help="业务类型, 1=语音通知 / 2=隐私号 / 3=智能外呼 等")
    sp.add_argument("--industry-type", type=int, help="行业类型枚举")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--offset", type=int, default=0)

    sp = sub.add_parser("update_qualification", help="更新资质 (UpdateQualification)")
    sp.add_argument("--qualification-id", required=True)
    sp.add_argument("--payload", required=True, help="变更字段 JSON")

    sp = sub.add_parser("upload_qualification_file",
                        help="上传资质材料 (UploadQualificationFileV2)")
    sp.add_argument("--file-url", required=True, help="公网可访问的材料 URL (图片/PDF)")
    sp.add_argument("--qualification-id", help="关联的资质 ID")
    sp.add_argument("--file-type", type=int,
                    help="材料类型枚举 (营业执照/身份证正反面 等, 由业务侧约定)")
    sp.add_argument("--file-name", help="材料展示名")

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
