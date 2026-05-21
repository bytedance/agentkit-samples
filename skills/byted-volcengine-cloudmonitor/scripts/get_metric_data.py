#!/usr/bin/env python3
from __future__ import print_function

import argparse
from datetime import datetime
import json
import os
import time


def _format_timestamp(timestamp):
    """将 Unix 秒级时间戳转换为本地可读时间。"""
    return datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M:%S")


def _decorate_response(resp):
    """为 CloudMonitor 返回结果补充可读时间字段，便于直接查看。"""
    if hasattr(resp, "to_dict"):
        data = resp.to_dict()
    else:
        data = resp

    if not isinstance(data, dict):
        return data

    payload = data.get("data")
    if not isinstance(payload, dict):
        return data

    start_time = payload.get("start_time")
    end_time = payload.get("end_time")
    if start_time is not None:
        payload["start_time_readable"] = _format_timestamp(start_time)
    if end_time is not None:
        payload["end_time_readable"] = _format_timestamp(end_time)

    for series in payload.get("metric_data_results", []) or []:
        for point in series.get("data_points", []) or []:
            timestamp = point.get("timestamp")
            if timestamp is not None:
                point["time"] = _format_timestamp(timestamp)

    return data


def _read_env_file(path):
    result = {}
    if not os.path.exists(path):
        return result
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                result[k.strip()] = v.strip()
    except Exception:
        pass
    return result


def _load_credentials(args):
    ak = args.ak or os.getenv("VOLCENGINE_AK", "")
    sk = args.sk or os.getenv("VOLCENGINE_SK", "")
    region = args.region or os.getenv("VOLCENGINE_REGION", "cn-beijing")

    if not ak or not sk:
        env_map = _read_env_file(os.path.expanduser("~/.openclaw/workspace/.env"))
        ak = ak or env_map.get("VOLCENGINE_AK", "")
        sk = sk or env_map.get("VOLCENGINE_SK", "")

    if not ak or not sk:
        config_path = os.path.expanduser("~/.volcengine/config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                ak = ak or cfg.get("ak", "")
                sk = sk or cfg.get("sk", "")
                region = region if region != "cn-beijing" else cfg.get("region", region)
            except Exception:
                pass

    if not ak or not sk:
        raise RuntimeError("未配置 AK/SK，请通过 --ak/--sk、环境变量 VOLCENGINE_ACCESS_KEY/SECRET_KEY 或 .env 文件提供。")

    return ak, sk, region


def main():
    parser = argparse.ArgumentParser(description="火山引擎云监控 - 查询监控时序数据")
    parser.add_argument("--namespace", "-n", required=True, help="产品命名空间（如 VCM_ECS）")
    parser.add_argument("--metric-name", "-m", required=True, help="监控指标名称（如 CPUUtilization）")
    parser.add_argument("--sub-namespace", "-s", required=True, help="子命名空间（如 Instance）")
    parser.add_argument("--dimension-name", "-d", required=True, help="维度名称（如 ResourceID）")
    parser.add_argument("--dimension-value", "-v", required=True, help="维度值（如实例 ID）")
    parser.add_argument("--start-time", type=int, help="开始时间戳（Unix 秒）")
    parser.add_argument("--end-time", type=int, help="结束时间戳（Unix 秒）")
    parser.add_argument("--duration", type=int, default=5, help="查询时长（分钟，默认 5）")
    parser.add_argument("--ak", help="Access Key")
    parser.add_argument("--sk", help="Secret Key")
    parser.add_argument("--region", default="cn-beijing", help="区域（默认 cn-beijing）")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    args = parser.parse_args()

    import volcenginesdkcore
    import volcenginesdkvolcobserve
    from volcenginesdkcore.rest import ApiException

    ak, sk, region = _load_credentials(args)

    configuration = volcenginesdkcore.Configuration()
    configuration.ak = ak
    configuration.sk = sk
    configuration.region = region
    volcenginesdkcore.Configuration.set_default(configuration)

    api_instance = volcenginesdkvolcobserve.VOLCOBSERVEApi()

    now = int(time.time())
    end_time = args.end_time if args.end_time is not None else now
    start_time = args.start_time if args.start_time is not None else (end_time - args.duration * 60)

    req_dimensions = volcenginesdkvolcobserve.DimensionForGetMetricDataInput(
        name=args.dimension_name,
        value=args.dimension_value,
    )
    req_instances = volcenginesdkvolcobserve.InstanceForGetMetricDataInput(
        dimensions=[req_dimensions],
    )
    request = volcenginesdkvolcobserve.GetMetricDataRequest(
        end_time=end_time,
        instances=[req_instances],
        metric_name=args.metric_name,
        namespace=args.namespace,
        start_time=start_time,
        sub_namespace=args.sub_namespace,
    )

    try:
        resp = api_instance.get_metric_data(request)
        decorated_resp = _decorate_response(resp)
        if args.json:
            print(json.dumps(decorated_resp, indent=2, ensure_ascii=False))
        else:
            payload = decorated_resp.get("data", {}) if isinstance(decorated_resp, dict) else {}
            print("=" * 60)
            print("CloudMonitor 监控时序数据")
            print("=" * 60)
            print(f"namespace:       {args.namespace}")
            print(f"metric_name:     {args.metric_name}")
            print(f"sub_namespace:   {args.sub_namespace}")
            print(f"{args.dimension_name}: {args.dimension_value}")
            print(f"time_range:      {_format_timestamp(start_time)} ~ {_format_timestamp(end_time)}")
            print("=" * 60)
            for series in payload.get("metric_data_results", []) or []:
                print(f"legend:          {series.get('legend', '-')}")
                for point in series.get("data_points", []) or []:
                    print(f"{point.get('time', '-')}  value={point.get('value')}")
                print("-" * 60)
    except ApiException as e:
        print(f"CloudMonitor GetMetricData 调用失败: {e}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
