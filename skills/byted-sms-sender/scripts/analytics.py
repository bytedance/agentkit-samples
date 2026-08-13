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
"""Customer-visible analytics for the external domestic SMS Actions.

This module intentionally uses only ``ListTotalSendCountStatForAgent`` and
``ListSmsSendLogForAgent``. It exposes only customer-visible fields and does
not infer or return non-public implementation data.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

SHANGHAI_TZ = datetime.timezone(datetime.timedelta(hours=8))
TIMEZONE_NAME = "Asia/Shanghai"
MAX_WINDOW = datetime.timedelta(days=90)
MAX_BUCKETS = 100
MAX_LOGICAL_QUERIES = 120
ALLOWED_DIMENSIONS = frozenset({"subAccount", "signature", "template", "time"})
SUCCESS_ERROR_CODES = frozenset({"", "0", "OK", "SUCCESS", "DELIVRD"})
CHANNEL_TYPES = frozenset({"CN_OTP", "CN_NTC", "CN_MKT"})
MOBILE_PATTERN = re.compile(r"^1[3-9]\d{9}$")


class AnalyticsError(ValueError):
    def __init__(self, message: str, code: str = "analytics_validation_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TimeWindow:
    start: datetime.datetime
    end: datetime.datetime
    timezone: str = TIMEZONE_NAME

    @property
    def start_epoch(self) -> int:
        return int(self.start.timestamp())

    @property
    def end_epoch(self) -> int:
        return int(self.end.timestamp())


def _parse_time(value: str, name: str) -> datetime.datetime:
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise AnalyticsError("{} must be an ISO 8601 timestamp".format(name)) from exc
    if parsed.microsecond:
        raise AnalyticsError("{} must have whole-second precision".format(name))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI_TZ)
    return parsed.astimezone(SHANGHAI_TZ)


def parse_window(start: str, end: str) -> TimeWindow:
    """Parse an explicit ``[start, end)`` window in Asia/Shanghai."""
    start_value = _parse_time(start, "start")
    end_value = _parse_time(end, "end")
    duration = end_value - start_value
    if duration <= datetime.timedelta(0):
        raise AnalyticsError("end must be later than start")
    if duration > MAX_WINDOW:
        raise AnalyticsError("analytics window must not exceed 90 days")
    return TimeWindow(start_value, end_value)


def time_buckets(window: TimeWindow, granularity: str) -> List[TimeWindow]:
    """Return stable local hour/day buckets, clipped to the requested window."""
    if granularity == "total":
        return [window]
    if granularity not in {"hour", "day"}:
        raise AnalyticsError("bucket must be one of: total, hour, day")

    if granularity == "hour":
        boundary = window.start.replace(minute=0, second=0) + datetime.timedelta(
            hours=1
        )
        step = datetime.timedelta(hours=1)
    else:
        boundary = window.start.replace(
            hour=0, minute=0, second=0
        ) + datetime.timedelta(days=1)
        step = datetime.timedelta(days=1)

    buckets: List[TimeWindow] = []
    cursor = window.start
    while cursor < window.end:
        bucket_end = min(boundary, window.end)
        buckets.append(TimeWindow(cursor, bucket_end))
        if len(buckets) > MAX_BUCKETS:
            raise AnalyticsError(
                "requested bucket size would exceed 100 aggregate queries"
            )
        cursor = bucket_end
        boundary += step
    return buckets


def validate_dimension(dimension: str) -> str:
    if dimension not in ALLOWED_DIMENSIONS:
        raise AnalyticsError(
            "dimension must be one of subAccount, signature, template, or time"
        )
    return dimension


def _nonnegative_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, float) and value >= 0 and value.is_integer():
        return int(value)
    return None


def _rate(
    numerator: Optional[int],
    denominator: Optional[int],
    numerator_field: str,
    denominator_field: str,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "status": "insufficient_data",
        "numerator": numerator,
        "denominator": denominator,
        "percentage": None,
        "numerator_field": numerator_field,
        "denominator_field": denominator_field,
    }
    if numerator is None or denominator is None or denominator == 0:
        return result
    if numerator > denominator:
        return result
    result["status"] = "available"
    result["percentage"] = round(numerator * 100.0 / denominator, 4)
    return result


def normalize_stats(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalize public aggregate fields without trusting service rate fields."""
    all_send = _nonnegative_int(raw.get("TotalAllSendCount"))
    send_success = _nonnegative_int(raw.get("TotalSendSuccessCount"))
    receipt_success = _nonnegative_int(raw.get("TotalReceiptSuccessCount"))
    receipt_failure = _nonnegative_int(raw.get("TotalReceiptFailureCount"))
    service_send_count = _nonnegative_int(raw.get("TotalSendCount"))

    receipts: Dict[str, Any] = {
        "status": "insufficient_data",
        "success": receipt_success,
        "failure": receipt_failure,
        "outstanding": None,
        "denominator": send_success,
        "denominator_field": "TotalSendSuccessCount",
    }
    if (
        send_success is not None
        and receipt_success is not None
        and receipt_failure is not None
        and receipt_success + receipt_failure <= send_success
    ):
        receipts["status"] = "available"
        receipts["outstanding"] = send_success - receipt_success - receipt_failure

    return {
        "service_reported_send_count": {
            "value": service_send_count,
            "source_field": "TotalSendCount",
            "semantic": "not_used_as_recipient_or_rate_denominator",
        },
        "submission_success_rate": _rate(
            send_success,
            all_send,
            "TotalSendSuccessCount",
            "TotalAllSendCount",
        ),
        "receipt_success_rate": _rate(
            receipt_success,
            send_success,
            "TotalReceiptSuccessCount",
            "TotalSendSuccessCount",
        ),
        "receipts": receipts,
    }


def _require_result(envelope: Mapping[str, Any], action: str) -> Mapping[str, Any]:
    if not envelope.get("success"):
        error = envelope.get("error")
        message = error.get("message") if isinstance(error, Mapping) else None
        raise AnalyticsError(
            str(message or "{} failed".format(action)),
            "analytics_query_failed",
        )
    result = envelope.get("result")
    if not isinstance(result, Mapping):
        raise AnalyticsError(
            "{} returned no public result".format(action),
            "analytics_query_failed",
        )
    return result


def _window_json(window: TimeWindow) -> Dict[str, Any]:
    return {
        "start_inclusive": window.start.isoformat(),
        "end_exclusive": window.end.isoformat(),
    }


def build_report(
    client: Any,
    *,
    start: str,
    end: str,
    sub_account: Optional[str] = None,
    channel_type: Optional[str] = None,
    signature: Optional[str] = None,
    template_id: Optional[str] = None,
    mobile: Optional[str] = None,
    bucket: str = "day",
    include_logs: bool = False,
    page_size: int = 100,
    max_pages: int = 10,
    dimension: str = "time",
) -> Dict[str, Any]:
    """Build aggregate trends and, when requested, safe send-log analysis."""
    window = parse_window(start, end)
    validate_dimension(dimension)
    if include_logs and not sub_account:
        raise AnalyticsError("send-log analysis requires sub-account")
    if channel_type and channel_type not in CHANNEL_TYPES:
        raise AnalyticsError("channel-type must be one of CN_OTP, CN_NTC, or CN_MKT")
    if channel_type and include_logs:
        raise AnalyticsError(
            "channel-type cannot be combined with send logs because "
            "ListSmsSendLogForAgent has no ChannelType request filter"
        )
    if mobile and not include_logs:
        raise AnalyticsError("mobile filter requires --include-logs")
    filters = {
        key: value
        for key, value in {
            "SubAccount": sub_account,
            "ChannelType": channel_type,
            "Signature": signature,
            "TemplateId": template_id,
        }.items()
        if value
    }
    buckets = time_buckets(window, bucket)
    requested_queries = len(buckets) + (max_pages if include_logs else 0)
    if requested_queries > MAX_LOGICAL_QUERIES:
        raise AnalyticsError(
            "aggregate buckets plus send-log pages must not exceed {} logical queries".format(
                MAX_LOGICAL_QUERIES
            )
        )
    trend: List[Dict[str, Any]] = []
    status = "complete"
    for item in buckets:
        params = {
            "StartTime": item.start_epoch,
            # The public Action accepts epoch seconds. Using the inclusive last
            # second prevents adjacent local buckets from overlapping.
            "EndTime": item.end_epoch - 1,
            **filters,
        }
        result = _require_result(
            client.call("ListTotalSendCountStatForAgent", params),
            "ListTotalSendCountStatForAgent",
        )
        metrics = normalize_stats(result)
        if (
            metrics["submission_success_rate"]["status"] == "insufficient_data"
            or metrics["receipt_success_rate"]["status"] == "insufficient_data"
            or metrics["receipts"]["status"] == "insufficient_data"
        ):
            status = "insufficient_data"
        trend.append({"window": _window_json(item), "metrics": metrics})

    report: Dict[str, Any] = {
        "status": status,
        "aggregate_population": "submission_level",
        "timezone": TIMEZONE_NAME,
        "window": _window_json(window),
        "data_cutoff_exclusive": window.end.isoformat(),
        "scope": {
            "subAccount": sub_account,
            "channelType": channel_type,
            "signature": signature,
            "templateId": template_id,
            "sendLogsMobileFilterApplied": bool(mobile),
        },
        "bucket": bucket,
        "trend": trend,
    }
    if include_logs:
        logs = fetch_send_logs(
            client,
            window,
            sub_account=sub_account,
            signature=signature,
            template_id=template_id,
            mobile=mobile,
            page_size=page_size,
            max_pages=max_pages,
        )
        logs["breakdown"] = group_records(logs["records"], dimension)
        logs["dimension"] = dimension
        report["send_logs"] = logs
        if logs["evidence_status"] != "complete":
            report["status"] = "insufficient_data"
    return report


def _list_items(result: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    raw = result.get("List")
    if raw is None:
        raw = result.get("list")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _value(item: Mapping[str, Any], upper: str, lower: str) -> Any:
    return item.get(upper) if upper in item else item.get(lower)


def _receipt_state(item: Mapping[str, Any]) -> str:
    error_code = str(_value(item, "ErrorCode", "errorCode") or "").strip()
    if error_code.upper() not in SUCCESS_ERROR_CODES:
        return "failure"
    receipt_time = _nonnegative_int(_value(item, "ReceiptTime", "receiptTime"))
    if receipt_time:
        return "success"
    return "outstanding"


def _safe_record(item: Mapping[str, Any]) -> Dict[str, Any]:
    count = _nonnegative_int(_value(item, "Count", "count"))
    return {
        "messageId": str(_value(item, "MessageId", "messageId") or ""),
        "sendTime": _nonnegative_int(_value(item, "SendTime", "sendTime")),
        "receiptTime": _nonnegative_int(_value(item, "ReceiptTime", "receiptTime")),
        "receiptState": _receipt_state(item),
        "errorCode": str(_value(item, "ErrorCode", "errorCode") or "").strip(),
        "segments": count if count and count > 0 else 1,
        "subAccount": str(_value(item, "SubAccount", "subAccount") or ""),
        "signature": str(_value(item, "Signature", "signature") or ""),
        "templateId": str(_value(item, "TemplateId", "templateId") or ""),
    }


def fetch_send_logs(
    client: Any,
    window: TimeWindow,
    *,
    sub_account: str,
    signature: Optional[str] = None,
    template_id: Optional[str] = None,
    mobile: Optional[str] = None,
    page_size: int = 100,
    max_pages: int = 10,
) -> Dict[str, Any]:
    """Fetch bounded public send logs with MessageId deduplication."""
    if not 1 <= page_size <= 100:
        raise AnalyticsError("page-size must be between 1 and 100")
    if not 1 <= max_pages <= 100:
        raise AnalyticsError("max-pages must be between 1 and 100")
    if not sub_account:
        raise AnalyticsError("sub-account is required for send-log analysis")
    if mobile and not MOBILE_PATTERN.fullmatch(mobile):
        raise AnalyticsError("mobile must be a mainland China mobile number")
    if window.end - window.start > MAX_WINDOW:
        raise AnalyticsError("send-log window must not exceed 90 days")

    records_by_id: Dict[str, Dict[str, Any]] = {}
    anonymous_records: List[Dict[str, Any]] = []
    duplicate_count = 0
    raw_fetched = 0
    total: Optional[int] = None
    complete = False
    pages_fetched = 0
    limitations: List[str] = []

    for page in range(1, max_pages + 1):
        pages_fetched = page
        params: Dict[str, Any] = {
            "SubAccount": sub_account,
            "FromTime": window.start_epoch,
            "ToTime": window.end_epoch - 1,
            "Page": page,
            "PageSize": page_size,
        }
        if signature:
            params["Signature"] = signature
        if template_id:
            params["TemplateId"] = template_id
        if mobile:
            params["Mobile"] = mobile
        result = _require_result(
            client.call("ListSmsSendLogForAgent", params),
            "ListSmsSendLogForAgent",
        )
        current_total = _nonnegative_int(result.get("Total"))
        if current_total is None:
            current_total = _nonnegative_int(result.get("total"))
        if current_total is not None:
            total = current_total if total is None else max(total, current_total)
        items = _list_items(result)
        raw_fetched += len(items)
        for raw in items:
            record = _safe_record(raw)
            message_id = record["messageId"]
            if not message_id:
                anonymous_records.append(record)
                if "missing_message_id" not in limitations:
                    limitations.append("missing_message_id")
            elif message_id in records_by_id:
                duplicate_count += 1
            else:
                records_by_id[message_id] = record

        evidence_count = len(records_by_id) + len(anonymous_records)
        if total is not None and evidence_count >= total:
            complete = True
            break
        if not items or len(items) < page_size:
            if total is None:
                complete = True
            else:
                limitations.append("service_total_not_reached")
            break

    if not complete:
        limitations.append("page_limit_reached")
    records = list(records_by_id.values()) + anonymous_records
    records.sort(
        key=lambda row: (
            row["sendTime"] is None,
            row["sendTime"] if row["sendTime"] is not None else 0,
            row["messageId"],
        )
    )
    receipt_states = {"success": 0, "failure": 0, "outstanding": 0}
    error_codes: Dict[str, Dict[str, Any]] = {}
    for record in records:
        receipt_states[record["receiptState"]] += 1
        code = record["errorCode"]
        if record["receiptState"] != "failure" or not code:
            continue
        entry = error_codes.setdefault(
            code,
            {
                "messages": 0,
                "segments": 0,
                "explanation": "unknown_public_code",
                "recommendation": "reconcile_with_the_customer_visible_send_log",
            },
        )
        entry["messages"] += 1
        entry["segments"] += record["segments"]

    evidence_status = "complete"
    if limitations:
        evidence_status = "insufficient_data"
    return {
        "population": "message_level",
        "complete": complete,
        "truncated": not complete,
        "evidence_status": evidence_status,
        "limitations": limitations,
        "pages_fetched": pages_fetched,
        "service_total": total,
        "raw_records_fetched": raw_fetched,
        "unique_records": len(records),
        "duplicate_count": duplicate_count,
        "receipt_states": receipt_states,
        "error_codes": dict(sorted(error_codes.items())),
        "records": records,
    }


def group_records(
    records: Sequence[Mapping[str, Any]], dimension: str
) -> List[Dict[str, Any]]:
    """Group already-sanitized records by an allowed customer dimension."""
    validate_dimension(dimension)
    groups: Dict[str, Dict[str, Any]] = {}
    field = {
        "subAccount": "subAccount",
        "signature": "signature",
        "template": "templateId",
    }.get(dimension)
    for record in records:
        if dimension == "time":
            timestamp = _nonnegative_int(record.get("sendTime"))
            if timestamp is None:
                value = "unknown"
            else:
                # Send-log responses use epoch milliseconds even though the
                # Action request window uses epoch seconds. Keep compatibility
                # with older second-based fixtures and responses.
                timestamp_seconds = (
                    timestamp / 1000 if timestamp >= 100_000_000_000 else timestamp
                )
                value = (
                    datetime.datetime.fromtimestamp(
                        timestamp_seconds, tz=SHANGHAI_TZ
                    )
                    .date()
                    .isoformat()
                )
        else:
            value = str(record.get(str(field)) or "unknown")
        group = groups.setdefault(
            value,
            {
                "value": value,
                "messages": 0,
                "segments": 0,
                "success": 0,
                "failure": 0,
                "outstanding": 0,
            },
        )
        group["messages"] += 1
        group["segments"] += _nonnegative_int(record.get("segments")) or 1
        state = str(record.get("receiptState"))
        if state in {"success", "failure", "outstanding"}:
            group[state] += 1
    return [groups[key] for key in sorted(groups)]
