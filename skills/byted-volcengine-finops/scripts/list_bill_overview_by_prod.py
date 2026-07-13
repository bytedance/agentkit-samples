#!/usr/bin/env python3
import argparse

import volcenginesdkbilling
from volcenginesdkcore.rest import ApiException

from common import DEFAULT_ENV_PATH, build_billing_api, build_request_from_official_kwargs, print_response, validate_month, validate_pagination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="分页查询产品维度账单总览信息")
    parser.add_argument("--BillPeriod", "--bill-period", dest="bill_period", required=True, help="账期，格式为 YYYY-MM")
    parser.add_argument("--Limit", "--limit", dest="limit", type=int, required=True, help="单页数量，范围 [1,300]")
    parser.add_argument("--Offset", "--offset", dest="offset", type=int, default=argparse.SUPPRESS, help="分页偏移量")
    parser.add_argument("--NeedRecordNum", "--need-record-num", dest="need_record_num", type=int, choices=[0, 1], default=argparse.SUPPRESS, help="是否返回总数")
    parser.add_argument("--IgnoreZero", "--ignore-zero", dest="ignore_zero", type=int, choices=[0, 1], default=argparse.SUPPRESS, help="是否忽略零金额数据")
    parser.add_argument("--BillCategoryParent", "--bill-category-parent", dest="bill_category_parent", action="append", help="账单大类，可重复传入")
    parser.add_argument("--BillingMode", "--billing-mode", dest="billing_mode", action="append", help="计费模式，可重复传入")
    parser.add_argument("--Product", "--product", dest="product", action="append", help="产品名称，可重复传入")
    parser.add_argument("--PayerID", "--payer-id", dest="payer_id", type=int, action="append", help="Payer 账号 ID，可重复传入")
    parser.add_argument("--OwnerID", "--owner-id", dest="owner_id", type=int, action="append", help="Owner 账号 ID，可重复传入")
    parser.add_argument("--region", default="", help="地域，默认读取 VOLCENGINE_REGION")
    parser.add_argument("--env-path", default=DEFAULT_ENV_PATH, help="可选 .env 文件路径")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    validate_month(args.bill_period, "BillPeriod")
    validate_pagination(args.limit, getattr(args, "offset", 0))
    api_instance = build_billing_api(args.env_path, args.region)
    request = build_request_from_official_kwargs(
        volcenginesdkbilling.ListBillOverviewByProdRequest,
        {
            "BillPeriod": args.bill_period,
            "Limit": args.limit,
            "Offset": getattr(args, "offset", None),
            "NeedRecordNum": getattr(args, "need_record_num", None),
            "IgnoreZero": getattr(args, "ignore_zero", None),
            "BillCategoryParent": getattr(args, "bill_category_parent", None),
            "BillingMode": getattr(args, "billing_mode", None),
            "Product": getattr(args, "product", None),
            "PayerID": getattr(args, "payer_id", None),
            "OwnerID": getattr(args, "owner_id", None),
        },
    )
    try:
        response = api_instance.list_bill_overview_by_prod(request)
        print_response(response)
    except ApiException as exc:
        raise SystemExit(f"ListBillOverviewByProd 调用失败: {exc}")


if __name__ == "__main__":
    main()
