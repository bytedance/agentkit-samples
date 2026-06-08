# Copyright (c) 2026 ByteDance
# SPDX-License-Identifier: MIT

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Iterable, List

from .models import ConnectivityCheck, RuntimeConfig


KNOWN_DATASOURCES = {"prometheus", "loki", "tempo", "internal_tsdb", "mixed", "grafana"}


def _auth_headers(runtime: RuntimeConfig) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if runtime.prom_bearer:
        headers["Authorization"] = f"Bearer {runtime.prom_bearer}"
    elif runtime.prom_username and runtime.prom_password:
        token = base64.b64encode(f"{runtime.prom_username}:{runtime.prom_password}".encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {token}"
    return headers


def _check_prometheus_query_api(runtime: RuntimeConfig) -> tuple[bool, str]:
    if not runtime.prom_url:
        return False, "prom_url missing"

    base = runtime.prom_url.rstrip("/")
    url = f"{base}/api/v1/query?{urllib.parse.urlencode({'query': '1'})}"
    request = urllib.request.Request(url, method="GET", headers=_auth_headers(runtime))
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if payload.get("status") in {None, "success"}:
                return True, "prometheus query api reachable"
            return False, f"prometheus status={payload.get('status')}"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return False, f"prometheus query api unreachable: {exc}"


def _check_grafana_query_api(runtime: RuntimeConfig) -> tuple[bool, str]:
    if not (runtime.grafana_url and runtime.grafana_token and runtime.datasource_uid):
        return False, "grafana credentials or datasource uid missing"

    url = runtime.grafana_url.rstrip("/") + "/api/ds/query"
    payload = {
        "queries": [
            {
                "refId": "A",
                "datasource": {"uid": runtime.datasource_uid},
                "datasourceUid": runtime.datasource_uid,
                "expr": "1",
                "intervalMs": 30000,
                "maxDataPoints": 10,
            }
        ],
        "from": "now-5m",
        "to": "now",
    }
    request = urllib.request.Request(
        url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {runtime.grafana_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            _ = json.loads(response.read().decode("utf-8"))
            return True, "grafana query api reachable"
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        return False, f"grafana query api unreachable: {exc}"


def run_connectivity_checks(datasources: Iterable[str], runtime: RuntimeConfig) -> List[ConnectivityCheck]:
    checks: List[ConnectivityCheck] = []

    normalized = sorted({(name or "prometheus").lower().replace(" ", "_") for name in datasources})
    if not normalized:
        normalized = ["prometheus"]

    for datasource in normalized:
        exists = datasource in KNOWN_DATASOURCES

        if runtime.offline:
            credentials_ok = True
            query_api_ok = True
            message = "offline mode: runtime api checks skipped"
        elif datasource == "prometheus":
            credentials_ok = bool(runtime.prom_url or (runtime.grafana_url and runtime.grafana_token and runtime.datasource_uid))
            if runtime.prom_url:
                query_api_ok, message = _check_prometheus_query_api(runtime)
            else:
                query_api_ok, message = _check_grafana_query_api(runtime)
        else:
            credentials_ok = bool(runtime.grafana_url and runtime.grafana_token and runtime.datasource_uid)
            query_api_ok, message = _check_grafana_query_api(runtime)

        if not exists:
            status = "failed"
            message = f"unknown datasource: {datasource}"
        elif not credentials_ok:
            status = "failed"
            message = "credentials unavailable"
        elif not query_api_ok:
            status = "failed"
        else:
            status = "ok"

        checks.append(
            ConnectivityCheck(
                datasource=datasource,
                exists=exists,
                credentials_ok=credentials_ok,
                query_api_ok=query_api_ok,
                status=status,
                message=message,
            )
        )

    return checks
