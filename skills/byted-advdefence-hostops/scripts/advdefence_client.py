# -*- coding: utf-8 -*-
"""Reusable AdvDefence client and helper entrypoints for the byted-advdefence-hostops skill."""

import datetime
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests


SERVICE = "advdefence"
REGION = "cn-beijing"
HOST = "open.volcengineapi.com"
ENDPOINT = f"https://{HOST}"


ACTION_META = {
    "GetHostDefStatus": ("2021-06-15", "GET"),
    "DescSmartCCConf": ("2021-06-15", "GET"),
    "DescWebDefCcRule": ("2021-06-15", "GET"),
    "GetWafAllowList": ("2021-06-15", "GET"),
    "GetWafBlockList": ("2021-06-15", "GET"),
    "DescWebDefBanRegion": ("2021-06-15", "GET"),
    "DescribeAttackEvent": ("2023-03-08", "POST"),
    "ExportAttackEvents": ("2021-06-15", "POST"),
    "DescribeEvent": ("2021-06-15", "POST"),
    "DescribeTopAttackSrcIp": ("2021-06-15", "GET"),
    "DescribeTopAttackSrcArea": ("2021-06-15", "GET"),
    "DescribeTopAttackSrcInfo": ("2021-06-15", "GET"),
    "DescribeAttackDistribution": ("2021-06-15", "GET"),
    "DescWebAtkOverview": ("2021-06-15", "POST"),
    "DescWebAtkTopSrcIp": ("2021-06-15", "POST"),
    "DescWebAtkTopUrl": ("2021-06-15", "POST"),
    "DescribeAttackFlow": ("2021-06-15", "POST"),
    "DescribeBizFlowAndConnCount": ("2023-03-08", "POST"),
    "DescWebBpsFlow": ("2021-06-15", "POST"),
    "DescWebQpsFlow": ("2021-06-15", "POST"),
    "DescWebRespCode": ("2021-06-15", "POST"),
    "DescWebAtkStatistics": ("2021-06-15", "POST"),
    "DescWebDisplayPhase": ("2021-06-15", "GET"),
    "DescHostRules": ("2021-06-15", "GET"),
    "ListAssets": ("2021-06-15", "POST"),
    "ListEvents": ("2021-06-15", "POST"),
    "ListRecommendations": ("2021-06-15", "POST"),
    "DescribeRecommendation": ("2021-06-15", "POST"),
}


_HEADER_KEY_MAP = {
    "host": "Host",
    "x-content-sha256": "X-Content-Sha256",
    "x-date": "X-Date",
    "content-type": "Content-Type",
}


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    k_date = _hmac_sha256(secret_key.encode("utf-8"), date_stamp)
    k_region = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    return _hmac_sha256(k_service, "request")


def _canonical_query(params: Dict[str, Any]) -> str:
    items = []
    for key in sorted(params.keys()):
        value = params[key]
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            value = ",".join(str(item) for item in value)
        items.append((quote(str(key), safe="-_.~"), quote(str(value), safe="-_.~")))
    return "&".join(f"{key}={value}" for key, value in items)


def call_advdefence(
    action: str,
    version: str,
    body: Optional[Dict[str, Any]],
    access_key: str,
    secret_key: str,
    region: str = REGION,
    service: str = SERVICE,
    host: str = HOST,
    method: str = "POST",
    timeout: int = 15,
) -> Tuple[int, Dict[str, Any]]:
    query: Dict[str, Any] = {"Action": action, "Version": version}

    if method == "GET":
        if body:
            query.update(body)
        body_bytes = b""
        content_type = "application/x-www-form-urlencoded"
    else:
        body_bytes = json.dumps(body or {}, separators=(",", ":")).encode("utf-8")
        content_type = "application/json"

    now = datetime.datetime.now(datetime.timezone.utc)
    x_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    body_hash = _sha256_hex(body_bytes)

    headers = {
        "Host": host,
        "X-Content-Sha256": body_hash,
        "X-Date": x_date,
        "Content-Type": content_type,
    }
    signed_list = ["content-type", "host", "x-content-sha256", "x-date"]
    canonical_headers = "".join(f"{item}:{headers[_HEADER_KEY_MAP[item]]}\n" for item in signed_list)
    signed_headers = ";".join(signed_list)

    canonical_request = "\n".join([
        method,
        "/",
        _canonical_query(query),
        canonical_headers,
        signed_headers,
        body_hash,
    ])
    credential_scope = f"{date_stamp}/{region}/{service}/request"
    string_to_sign = "\n".join([
        "HMAC-SHA256",
        x_date,
        credential_scope,
        _sha256_hex(canonical_request.encode("utf-8")),
    ])
    signing_key = _signing_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    headers["Authorization"] = (
        f"HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    url = f"https://{host}/?{_canonical_query(query)}"
    if method == "GET":
        response = requests.get(url, headers=headers, timeout=timeout)
    else:
        response = requests.post(url, headers=headers, data=body_bytes, timeout=timeout)

    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, {"raw": response.text}


class _BaseAdvDefenceClient:
    def __init__(self, access_key: str, secret_key: str):
        self.ak = access_key
        self.sk = secret_key

    def _call(self, action: str, body: Optional[Dict[str, Any]] = None):
        version, method = ACTION_META[action]
        return call_advdefence(action, version, body, self.ak, self.sk, method=method)

    def desc_host_rules(
        self,
        host: Optional[str] = None,
        hosts: Optional[List[str]] = None,
        instance_ip: Optional[str] = None,
        instance_ips: Optional[List[str]] = None,
        demension: int = 1,
        accurate: int = 1,
        curr_page: int = 1,
        page_size: int = 20,
    ):
        body = {"Demension": demension, "Accurate": accurate, "CurrPage": curr_page, "PageSize": page_size}
        if host is not None:
            body["Host"] = host
        if hosts is not None:
            body["Hosts"] = hosts
        if instance_ip is not None:
            body["InstanceIp"] = instance_ip
        if instance_ips is not None:
            body["InstanceIps"] = instance_ips
        return self._call("DescHostRules", body)

    def resolve_instance_ips(self, host: str) -> List[str]:
        status, response = self.desc_host_rules(host=host, demension=1, accurate=1)
        if status != 200:
            raise RuntimeError(f"DescHostRules HTTP {status}: {response}")
        rules = (response.get("Result") or {}).get("RuleList") or []
        if not rules:
            raise RuntimeError(f"域名 {host} 未接入或不存在（请检查 Demension 是否传 1）")
        instance_ips: List[str] = []
        seen = set()
        for rule in rules:
            for instance_ip in rule.get("DefIp") or []:
                if instance_ip and instance_ip not in seen:
                    seen.add(instance_ip)
                    instance_ips.append(instance_ip)
        if not instance_ips:
            raise RuntimeError(f"域名 {host} 没有关联的高防实例 IP")
        return instance_ips


class HostPolicyClient(_BaseAdvDefenceClient):
    def get_host_def_status(self, host: str):
        return self._call("GetHostDefStatus", {"Host": host})

    def desc_smart_cc_conf(self, domain: str):
        return self._call("DescSmartCCConf", {"Domain": domain})

    def desc_web_def_cc_rule(
        self,
        host: str,
        cc_rule_name: Optional[str] = None,
        cc_rule_tag: Optional[str] = None,
        curr_page: int = 1,
        page_size: int = 20,
    ):
        body = {"Host": host, "CurrPage": curr_page, "PageSize": page_size}
        if cc_rule_name is not None:
            body["CCRuleName"] = cc_rule_name
        if cc_rule_tag is not None:
            body["CCRuleTag"] = cc_rule_tag
        return self._call("DescWebDefCcRule", body)

    def get_waf_allow_list(self, host: str, curr_page: int = 1, page_size: int = 20):
        return self._call("GetWafAllowList", {"Host": host, "CurrPage": curr_page, "PageSize": page_size})

    def get_waf_block_list(self, host: str, curr_page: int = 1, page_size: int = 20):
        return self._call("GetWafBlockList", {"Host": host, "CurrPage": curr_page, "PageSize": page_size})

    def desc_web_def_ban_region(self, host: str):
        return self._call("DescWebDefBanRegion", {"Host": host})

    def overview(self, host: str) -> Dict[str, Any]:
        output: Dict[str, Any] = {"Host": host}
        _safe_collect(output, "DefSwitch", self.get_host_def_status, host)
        _safe_collect(output, "SmartCCConf", self.desc_smart_cc_conf, host)
        _safe_collect(output, "CCRules", self.desc_web_def_cc_rule, host)
        _safe_collect(output, "WafAllowList", self.get_waf_allow_list, host)
        _safe_collect(output, "WafBlockList", self.get_waf_block_list, host)
        _safe_collect(output, "WebDefBanRegion", self.desc_web_def_ban_region, host)
        return output


class AttackEventClient(_BaseAdvDefenceClient):
    def describe_attack_event(self, begin_time: int, end_time: int, instance_ips: List[str], curr_page: int = 1, page_size: int = 20):
        return self._call("DescribeAttackEvent", {
            "BeginTime": begin_time,
            "EndTime": end_time,
            "InstanceIps": instance_ips,
            "CurrPage": curr_page,
            "PageSize": page_size,
        })

    def describe_top_attack_src_ip(self, begin_time: int, end_time: int, instance_ip: str, curr_page: int = 1, page_size: int = 20, time_zone: str = ""):
        body = {"BeginTime": begin_time, "EndTime": end_time, "InstanceIp": instance_ip, "CurrPage": curr_page, "PageSize": page_size}
        if time_zone:
            body["TimeZone"] = time_zone
        return self._call("DescribeTopAttackSrcIp", body)

    def describe_top_attack_src_area(self, begin_time: int, end_time: int, instance_ip: str, curr_page: int = 1, page_size: int = 20, time_zone: str = ""):
        body = {"BeginTime": begin_time, "EndTime": end_time, "InstanceIp": instance_ip, "CurrPage": curr_page, "PageSize": page_size}
        if time_zone:
            body["TimeZone"] = time_zone
        return self._call("DescribeTopAttackSrcArea", body)

    def describe_top_attack_src_info(self, begin_time: int, end_time: int, instance_ip: str, curr_page: int = 1, page_size: int = 20, time_zone: str = ""):
        body = {"BeginTime": begin_time, "EndTime": end_time, "InstanceIp": instance_ip, "CurrPage": curr_page, "PageSize": page_size}
        if time_zone:
            body["TimeZone"] = time_zone
        return self._call("DescribeTopAttackSrcInfo", body)

    def describe_attack_distribution(self, begin_time: int, end_time: int, instance_ip: str, curr_page: int = 1, page_size: int = 20, time_zone: str = ""):
        body = {"BeginTime": begin_time, "EndTime": end_time, "InstanceIp": instance_ip, "CurrPage": curr_page, "PageSize": page_size}
        if time_zone:
            body["TimeZone"] = time_zone
        return self._call("DescribeAttackDistribution", body)

    def desc_web_atk_overview(self, hosts: List[str], begin_time: int, end_time: int):
        return self._call("DescWebAtkOverview", {"Hosts": hosts, "BeginTime": begin_time, "EndTime": end_time})

    def desc_web_atk_top_src_ip(self, hosts: List[str], begin_time: int, end_time: int):
        return self._call("DescWebAtkTopSrcIp", {"Hosts": hosts, "BeginTime": begin_time, "EndTime": end_time})

    def desc_web_atk_top_url(self, hosts: List[str], begin_time: int, end_time: int):
        return self._call("DescWebAtkTopUrl", {"Hosts": hosts, "BeginTime": begin_time, "EndTime": end_time})

    def _collect_per_instance(self, fn, begin_time: int, end_time: int, instance_ips: List[str]) -> Dict[str, Any]:
        output: Dict[str, Any] = {}
        for instance_ip in instance_ips:
            try:
                status, response = fn(begin_time, end_time, instance_ip)
                metadata = response.get("ResponseMetadata") or {}
                if status != 200:
                    output[instance_ip] = {"http_status": status, "error": response}
                elif metadata.get("Error"):
                    output[instance_ip] = {"http_status": status, "error": metadata["Error"]}
                else:
                    output[instance_ip] = response.get("Result")
            except Exception as exc:
                output[instance_ip] = {"error": str(exc)}
        return output

    def overview(self, host: str, begin_time: int, end_time: int) -> Dict[str, Any]:
        output: Dict[str, Any] = {"Host": host, "BeginTime": begin_time, "EndTime": end_time}
        try:
            instance_ips = self.resolve_instance_ips(host)
            output["InstanceIps"] = instance_ips
        except Exception as exc:
            output["InstanceIps"] = {"error": str(exc)}
            instance_ips = []

        _safe_collect(output, "WebAtkOverview", self.desc_web_atk_overview, [host], begin_time, end_time)
        _safe_collect(output, "WebAtkTopSrcIp", self.desc_web_atk_top_src_ip, [host], begin_time, end_time)
        _safe_collect(output, "WebAtkTopUrl", self.desc_web_atk_top_url, [host], begin_time, end_time)

        if instance_ips:
            _safe_collect(output, "DDoSAttackEvent", self.describe_attack_event, begin_time, end_time, instance_ips)
            output["TopAttackSrcIp"] = self._collect_per_instance(self.describe_top_attack_src_ip, begin_time, end_time, instance_ips)
            output["TopAttackSrcArea"] = self._collect_per_instance(self.describe_top_attack_src_area, begin_time, end_time, instance_ips)
            output["AttackDistribution"] = self._collect_per_instance(self.describe_attack_distribution, begin_time, end_time, instance_ips)

        return output


class CCAIClient(_BaseAdvDefenceClient):
    def list_assets(self, domain: str, ai_defense_status: Optional[str] = None):
        body = {"Domain": domain}
        if ai_defense_status is not None:
            body["AiDefenseStatus"] = ai_defense_status
        return self._call("ListAssets", body)

    def list_events(
        self,
        domain: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        status: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
    ):
        body: Dict[str, Any] = {"Domain": domain, "PageNumber": page_number, "PageSize": page_size}
        if start_time is not None:
            body["StartTime"] = start_time
        if end_time is not None:
            body["EndTime"] = end_time
        if status is not None:
            body["Status"] = status
        return self._call("ListEvents", body)

    def list_recommendations(
        self,
        domain: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        status: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
    ):
        body: Dict[str, Any] = {"Domain": domain, "PageNumber": page_number, "PageSize": page_size}
        if start_time is not None:
            body["StartTime"] = start_time
        if end_time is not None:
            body["EndTime"] = end_time
        if status is not None:
            body["Status"] = status
        return self._call("ListRecommendations", body)

    def describe_event(self, event_id: str):
        return self._call("DescribeEvent", {"EventId": event_id})

    def describe_recommendation(self, recommendation_id: str):
        return self._call("DescribeRecommendation", {"RecommendationId": recommendation_id})

    def overview(self, domain: str) -> Dict[str, Any]:
        output: Dict[str, Any] = {"Domain": domain}
        _safe_collect(output, "Assets", self.list_assets, domain)
        _safe_collect(output, "Events", self.list_events, domain)
        _safe_collect(output, "Recommendations", self.list_recommendations, domain)
        return output


class FlowTrafficClient(_BaseAdvDefenceClient):
    def describe_attack_flow(self, instance_ips: List[str], begin_time: int, end_time: int, tab: str = "Peak"):
        return self._call("DescribeAttackFlow", {"InstanceIps": instance_ips, "BeginTime": begin_time, "EndTime": end_time, "Tab": tab})

    def describe_biz_flow_and_conn_count(self, instance_ips: List[str], begin_time: int, end_time: int):
        return self._call("DescribeBizFlowAndConnCount", {"InstanceIps": instance_ips, "BeginTime": begin_time, "EndTime": end_time})

    def desc_web_bps_flow(self, hosts: List[str], begin_time: int, end_time: int):
        return self._call("DescWebBpsFlow", {"Hosts": hosts, "BeginTime": begin_time, "EndTime": end_time})

    def desc_web_qps_flow(self, hosts: List[str], begin_time: int, end_time: int):
        return self._call("DescWebQpsFlow", {"Hosts": hosts, "BeginTime": begin_time, "EndTime": end_time})

    def desc_web_resp_code(self, hosts: List[str], begin_time: int, end_time: int, type_: int = 2):
        return self._call("DescWebRespCode", {"Hosts": hosts, "BeginTime": begin_time, "EndTime": end_time, "Type": type_})

    def desc_web_atk_statistics(self, hosts: List[str], begin_time: int, end_time: int):
        return self._call("DescWebAtkStatistics", {"Hosts": hosts, "BeginTime": begin_time, "EndTime": end_time})

    def overview(self, host: str, begin_time: int, end_time: int) -> Dict[str, Any]:
        output: Dict[str, Any] = {"Host": host, "BeginTime": begin_time, "EndTime": end_time}
        try:
            instance_ips = self.resolve_instance_ips(host)
            output["InstanceIps"] = instance_ips
        except Exception as exc:
            output["InstanceIps"] = {"error": str(exc)}
            instance_ips = []

        _safe_collect(output, "WebBpsFlow", self.desc_web_bps_flow, [host], begin_time, end_time)
        _safe_collect(output, "WebQpsFlow", self.desc_web_qps_flow, [host], begin_time, end_time)
        _safe_collect(output, "WebRespCode", self.desc_web_resp_code, [host], begin_time, end_time)
        _safe_collect(output, "WebAtkStatistics", self.desc_web_atk_statistics, [host], begin_time, end_time)

        if instance_ips:
            _safe_collect(output, "AttackFlowPeak", self.describe_attack_flow, instance_ips, begin_time, end_time, "Peak")
            _safe_collect(output, "BizFlowAndConnCount", self.describe_biz_flow_and_conn_count, instance_ips, begin_time, end_time)

        return output


def _safe_collect(output: Dict[str, Any], key: str, fn, *args, **kwargs) -> None:
    try:
        status, response = fn(*args, **kwargs)
        metadata = response.get("ResponseMetadata") or {}
        request_id = metadata.get("RequestId")
        if status != 200:
            output[key] = {"http_status": status, "error": response, "request_id": request_id}
        elif metadata.get("Error"):
            output[key] = {"http_status": status, "error": metadata["Error"], "request_id": request_id}
        else:
            output[key] = response.get("Result")
    except Exception as exc:
        output[key] = {"error": str(exc)}


def _get_credentials() -> Tuple[str, str]:
    resolved_ak = os.environ.get("VOLC_ACCESS_KEY")
    resolved_sk = os.environ.get("VOLC_SECRET_KEY")
    if not resolved_ak or not resolved_sk:
        raise RuntimeError(
            "缺少凭证：请通过环境变量 VOLC_ACCESS_KEY / VOLC_SECRET_KEY 注入火山引擎凭证。"
        )
    return resolved_ak, resolved_sk


def _wrap(fn, *args, **kwargs) -> Dict[str, Any]:
    try:
        return {"ok": True, "data": fn(*args, **kwargs)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "type": type(exc).__name__}


def query_advdefence_policy_overview(host: str) -> Dict[str, Any]:
    """Query read-only AdvDefence policy status for a protected host."""

    def run() -> Dict[str, Any]:
        access_key, secret_key = _get_credentials()
        return HostPolicyClient(access_key, secret_key).overview(host)

    return _wrap(run)


def query_advdefence_attack_events(
    host: str,
    begin_time: Optional[int] = None,
    end_time: Optional[int] = None,
    lookback_seconds: int = 3600,
) -> Dict[str, Any]:
    """Query recent AdvDefence attack observations for a protected host."""

    def run() -> Dict[str, Any]:
        access_key, secret_key = _get_credentials()
        end_ts = end_time if end_time is not None else int(time.time())
        begin_ts = begin_time if begin_time is not None else end_ts - lookback_seconds
        return AttackEventClient(access_key, secret_key).overview(host, begin_ts, end_ts)

    return _wrap(run)


def query_advdefence_flow_traffic(
    host: str,
    begin_time: Optional[int] = None,
    end_time: Optional[int] = None,
    lookback_seconds: int = 3600,
) -> Dict[str, Any]:
    """Query AdvDefence traffic, response-code, and connection observations."""

    def run() -> Dict[str, Any]:
        access_key, secret_key = _get_credentials()
        end_ts = end_time if end_time is not None else int(time.time())
        begin_ts = begin_time if begin_time is not None else end_ts - lookback_seconds
        return FlowTrafficClient(access_key, secret_key).overview(host, begin_ts, end_ts)

    return _wrap(run)


def resolve_advdefence_instance_ips(host: str) -> Dict[str, Any]:
    """Resolve a protected host to its associated AdvDefence instance IPs."""

    def run() -> List[str]:
        access_key, secret_key = _get_credentials()
        return HostPolicyClient(access_key, secret_key).resolve_instance_ips(host)

    return _wrap(run)


def query_advdefence_ccai_overview(host: str) -> Dict[str, Any]:
    """Query read-only CCAI asset, event, and recommendation status."""

    def run() -> Dict[str, Any]:
        access_key, secret_key = _get_credentials()
        return CCAIClient(access_key, secret_key).overview(host)

    return _wrap(run)


def query_advdefence_host_healthcheck(
    host: str,
    begin_time: Optional[int] = None,
    end_time: Optional[int] = None,
    lookback_seconds: int = 3600,
) -> Dict[str, Any]:
    """Run a read-only AdvDefence host health check across policy, events, traffic, and CCAI."""

    def run() -> Dict[str, Any]:
        access_key, secret_key = _get_credentials()
        end_ts = end_time if end_time is not None else int(time.time())
        begin_ts = begin_time if begin_time is not None else end_ts - lookback_seconds
        policy = HostPolicyClient(access_key, secret_key).overview(host)
        events = AttackEventClient(access_key, secret_key).overview(host, begin_ts, end_ts)
        traffic = FlowTrafficClient(access_key, secret_key).overview(host, begin_ts, end_ts)
        ccai = CCAIClient(access_key, secret_key).overview(host)
        return {
            "Host": host,
            "Window": {"BeginTime": begin_ts, "EndTime": end_ts},
            "Policy": policy,
            "Events": events,
            "Traffic": traffic,
            "CCAI": ccai,
        }

    return _wrap(run)
