#!/usr/bin/env python3
import argparse

import volcenginesdkbilling
from volcenginesdkcore.rest import ApiException

from common import DEFAULT_ENV_PATH, build_billing_api, build_request_from_official_kwargs, print_response, validate_month


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="查询账号维度账单总览信息")
    parser.add_argument("--BillPeriod", "--bill-period", dest="bill_period", required=True, help="账期，格式为 YYYY-MM")
    parser.add_argument("--BillCategoryParent", "--bill-category-parent", dest="bill_category_parent", action="append", help="账单大类，可重复传入")
    parser.add_argument("--BillingMode", "--billing-mode", dest="billing_mode", action="append", help="计费模式，可重复传入")
    parser.add_argument("--PayerID", "--payer-id", dest="payer_id", type=int, action="append", help="Payer 账号 ID，可重复传入")
    parser.add_argument("--OwnerID", "--owner-id", dest="owner_id", type=int, action="append", help="Owner 账号 ID，可重复传入")
    parser.add_argument("--region", default="", help="地域，默认读取 VOLCENGINE_REGION")
    parser.add_argument("--env-path", default=DEFAULT_ENV_PATH, help="可选 .env 文件路径")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    validate_month(args.bill_period, "BillPeriod")
    api_instance = build_billing_api(args.env_path, args.region)
    request = build_request_from_official_kwargs(
        volcenginesdkbilling.ListBillOverviewByCategoryRequest,
        {
            "BillPeriod": args.bill_period,
            "BillCategoryParent": args.bill_category_parent,
            "BillingMode": args.billing_mode,
            "PayerID": args.payer_id,
            "OwnerID": args.owner_id,
        },
    )
    try:
        response = api_instance.list_bill_overview_by_category(request)
        print_response(response)
    except ApiException as exc:
        raise SystemExit(f"ListBillOverviewByCategory 调用失败: {exc}")


if __name__ == "__main__":
    main()
