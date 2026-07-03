#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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
"""
火山云手机 OpenAPI 客户端
"""

import json
import hmac
import hashlib
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List, ClassVar
from datetime import datetime, timezone


class VePhoneClient:
    """火山云手机 API 客户端"""

    ACTION_VERSIONS: ClassVar[Dict[str, str]] = {
        "CreatePod": "2025-05-01",
        "ListPod": "2025-05-01",
        "DetailPod": "2025-05-01",
        "DeletePod": "2025-05-01",
        "UpdatePod": "2025-05-01",
        "PowerOnPod": "2025-05-01",
        "PowerOffPod": "2025-05-01",
        "RebootPod": "2025-05-01",
        "ResetPod": "2025-05-01",
        "InstallApp": "2025-05-01",
        "LaunchApp": "2025-05-01",
        "CloseApp": "2025-05-01",
        "UninstallApp": "2025-05-01",
        "GetPodAppList": "2025-05-01",
        "StartRecording": "2025-05-01",
        "StopRecording": "2025-05-01",
        "StartScreenShot": "2025-05-01",
        "BatchScreenShot": "2025-05-01",
        "StopScreenShot": "2025-05-01",
        "GetPreSignedEdgeURL": "2025-05-01",
        "PushFile": "2025-05-01",
        "PullFile": "2025-05-01",
        "RunCommand": "2025-05-01",
        "RunSyncCommand": "2025-05-01",
        "ListAOSPImage": "2025-05-01",
        "ListConfiguration": "2025-05-01",
        "ListPhoneTemplate": "2025-05-01",
        "ListDc": "2025-05-01",
        "ListPodResource": "2025-05-01",
        "GetProductResource": "2025-05-01",
        "ListOperableProduct": "2023-10-30",
        "ListPodResourceSet": "2025-05-01",
        "GetTaskInfo": "2025-05-01",
        "ListTask": "2025-05-01",
        "GetPodMetric": "2025-05-01",
        "GetPodProperty": "2025-05-01",
        "GetPhoneTemplate": "2025-05-01",
        "ListHost": "2025-05-01",
        "DetailHost": "2025-05-01",
        "UpdateHost": "2025-05-01",
        "RebootHost": "2025-05-01",
        "ResetHost": "2025-05-01",
        "ListImageResource": "2025-05-01",
        "GetImagePreheating": "2025-05-01",
        "GetDcBandwidthDailyPeak": "2025-05-01",
        "ListInstanceConfigurationSpec": "2025-05-01",
        "ListDisplayLayoutMini": "2025-05-01",
        "DetailDisplayLayoutMini": "2025-05-01",
        "DetailApp": "2025-05-01",
        "ListApp": "2025-05-01",
        "ListAppVersionDeploy": "2025-05-01",
        "GetAppCrashLog": "2025-05-01",
        "ListTag": "2025-05-01",
        "ListPortMappingRule": "2025-05-01",
        "DetailPortMappingRule": "2025-05-01",
        "ListDNSRule": "2025-05-01",
        "DetailDNSRule": "2025-05-01",
        "ListCustomRoute": "2025-05-01",
        "SubscribeResourceAuto": "2025-05-01",
        "RenewResourceAuto": "2025-05-01",
        "UnsubscribeHostResource": "2025-05-01",
        "CreatePodOneStep": "2025-05-01",
        "PodDataTransfer": "2025-05-01",
        "PodMute": "2025-05-01",
        "PodAdb": "2025-05-01",
        "PodStop": "2025-05-01",
        "PodDataDelete": "2025-05-01",
        "SetProxy": "2025-05-01",
        "GetProxy": "2025-05-01",
        "MigratePod": "2025-05-01",
        "BackupPod": "2025-05-01",
        "CancelBackupPod": "2025-05-01",
        "RestorePod": "2025-05-01",
        "CancelRestorePod": "2025-05-01",
        "BackupData": "2025-05-01",
        "RestoreData": "2025-05-01",
        "ListBackupData": "2025-05-01",
        "DeleteBackupData": "2025-05-01",
        "UpdatePodProperty": "2025-05-01",
        "AddPhoneTemplate": "2025-05-01",
        "UpdatePhoneTemplate": "2025-05-01",
        "RemovePhoneTemplate": "2025-05-01",
        "CreateImageOneStep": "2025-05-01",
        "BuildAOSPImage": "2025-05-01",
        "UpdateAOSPImage": "2025-05-01",
        "DeleteAOSPImage": "2025-05-01",
        "UpdatePodResourceApplyNum": "2025-05-01",
        "UpdateProductResource": "2025-05-01",
        "CreateDisplayLayoutMini": "2025-05-01",
        "DeleteDisplayLayout": "2025-05-01",
        "LaunchApps": "2025-05-01",
        "InstallApps": "2025-05-01",
        "UploadApp": "2025-05-01",
        "UpdateApp": "2025-05-01",
        "AutoInstallApp": "2025-05-01",
        "DeleteApp": "2025-05-01",
        "DeleteAppVersion": "2025-05-01",
        "BanUser": "2025-05-01",
        "CreateTag": "2025-05-01",
        "UpdateTag": "2025-05-01",
        "DeleteTag": "2025-05-01",
        "AttachTag": "2025-05-01",
        "CreatePortMappingRule": "2025-05-01",
        "BindPortMappingRule": "2025-05-01",
        "UnbindPortMappingRule": "2025-05-01",
        "CreateDNSRule": "2025-05-01",
        "UpdateDNSRule": "2025-05-01",
        "DeleteDNSRule": "2025-05-01",
        "AddCustomRoute": "2025-05-01",
        "DeleteCustomRoute": "2025-05-01",
        "UpdateCustomRoute": "2025-05-01",
    }

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        region: str = "cn-north-1",
        service: str = "ACEP",
        version: Optional[str] = None,
        product_id: Optional[str] = None,
        dc_id: Optional[str] = None,
        resource_type: Optional[int] = None,
        tos_bucket: Optional[str] = None,
        tos_region: Optional[str] = None,
        tos_endpoint: Optional[str] = None,
        tos_prefix: Optional[str] = None,
    ):
        """
        初始化客户端

        Args:
            access_key: 访问密钥
            secret_key: 秘密密钥
            region: 区域，默认 cn-north-1
            service: 服务名，默认 ACEP
            version: API 版本覆盖值（可选，默认按 Action 选择）
            product_id: 产品 ID（可选，可在调用时指定）
            dc_id: 机房 ID（可选，可在调用时指定）
            resource_type: 业务资源类型（云盘 100，本地存储 200）
            tos_bucket: TOS Bucket（可选，用于 PullFile 等接口）
            tos_region: TOS Region（可选）
            tos_endpoint: TOS Endpoint（可选）
            tos_prefix: TOS 对象路径前缀（可选）
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.service = service
        self.version = version
        self.product_id = product_id
        self.dc_id = dc_id
        self.resource_type = int(resource_type) if resource_type is not None else None
        self.tos_bucket = tos_bucket
        self.tos_region = tos_region
        self.tos_endpoint = tos_endpoint
        self.tos_prefix = tos_prefix or "cloudphone"
        self.host = "open.volcengineapi.com"
        self.base_url = f"https://{self.host}"

    @staticmethod
    def compact_body(**kwargs) -> Dict[str, Any]:
        return {key: value for key, value in kwargs.items() if value is not None}

    @staticmethod
    def _build_invocation_header(argv0: Optional[str] = None) -> Dict[str, str]:
        raw = argv0 if argv0 is not None else (sys.argv[0] if sys.argv else "")
        normalized = raw.replace("\\", "/")
        basename = os.path.basename(normalized)

        if basename == "vephone":
            return {"x-vephone-cli": "1"}
        if normalized == "scripts/vephone_cli.py" or normalized.endswith(
            "/scripts/vephone_cli.py"
        ):
            return {"x-vephone-skill": "1"}
        return {}

    def request_action(
        self,
        action: str,
        json_body: bool = False,
        version: Optional[str] = None,
        **body,
    ) -> Dict[str, Any]:
        payload = self.compact_body(**body)
        if json_body:
            return self._json_request(action, version=version, body=payload)
        return self._request(action, version=version, body=payload)

    def _sign_request(
        self,
        method: str,
        path: str,
        query_params: Optional[Dict[str, str]] = None,
        body: Optional[Any] = None,
    ) -> Dict[str, str]:
        """
        签名请求（火山引擎 v4 签名）

        Args:
            method: HTTP 方法
            path: 请求路径
            query_params: 查询参数
            body: 请求体

        Returns:
            包含签名的请求头
        """
        payload = self._serialize_payload(body)
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        invocation_headers = self._build_invocation_header()
        headers = {
            "Host": self.host,
            "Content-Type": "application/json",
            "X-Content-Sha256": payload_hash,
            **invocation_headers,
        }
        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        canonical_querystring = self._encode_query_params(query_params)

        canonical_uri = urllib.parse.quote(path, safe="/")
        canonical_header_map = {
            "content-type": "application/json",
            "host": self.host,
            "x-content-sha256": payload_hash,
            "x-date": amz_date,
            **invocation_headers,
        }
        signed_header_names = sorted(canonical_header_map)
        canonical_headers = "".join(
            f"{key}:{canonical_header_map[key]}\n" for key in signed_header_names
        )
        signed_headers = ";".join(signed_header_names)
        canonical_request = (
            f"{method}\n"
            f"{canonical_uri}\n"
            f"{canonical_querystring}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{payload_hash}"
        )

        algorithm = "HMAC-SHA256"
        credential_scope = f"{date_stamp}/{self.region}/{self.service}/request"
        string_to_sign = (
            f"{algorithm}\n"
            f"{amz_date}\n"
            f"{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )

        def sign(key, msg):
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        k_date = sign(self.secret_key.encode("utf-8"), date_stamp)
        k_region = sign(k_date, self.region)
        k_service = sign(k_region, self.service)
        k_signing = sign(k_service, "request")
        signature = sign(k_signing, string_to_sign).hex()

        headers.update(
            {
                "X-Date": amz_date,
                "Authorization": (
                    f"{algorithm} "
                    f"Credential={self.access_key}/{credential_scope}, "
                    f"SignedHeaders={signed_headers}, "
                    f"Signature={signature}"
                ),
            }
        )
        return headers

    @staticmethod
    def _serialize_payload(body: Optional[Any]) -> str:
        if isinstance(body, str):
            return body
        if body is None:
            return ""
        return json.dumps(body, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def _serialize_query_value(cls, value: Any) -> str:
        if isinstance(value, (dict, list)):
            return cls._serialize_payload(value)
        return str(value)

    @staticmethod
    def _encode_query_params(query_params: Optional[Dict[str, Any]]) -> str:
        if not query_params:
            return ""
        return "&".join(
            [
                f"{urllib.parse.quote(str(key), safe='-_.~')}"
                f"={urllib.parse.quote(str(value), safe='-_.~')}"
                for key, value in sorted(query_params.items())
            ]
        )

    def _request(
        self,
        action: str,
        version: Optional[str] = None,
        body: Optional[Dict[str, Any]] = None,
        method: str = "POST",
    ) -> Dict[str, Any]:
        """
        发送 API 请求

        Args:
            action: API 动作名称
            version: API 版本（可选，默认使用初始化时的版本）
            body: 请求体
            method: HTTP 方法

        Returns:
            API 响应
        """
        path = "/"

        if version is None:
            version = self.ACTION_VERSIONS.get(action, self.version)
        if version is None:
            raise ValueError(f"Missing API version for action: {action}")

        body = dict(body or {})
        body["Action"] = action
        body["Version"] = version

        # 将参数转换为查询字符串
        query_params = {}
        for key, value in body.items():
            if value is not None:
                query_params[key] = self._serialize_query_value(value)

        # 签名请求
        headers = self._sign_request(method, path, query_params, None)

        result = self._send_http_request(
            method=method,
            path=path,
            headers=headers,
            query_params=query_params,
            body=None,
        )

        # 检查错误
        if "ResponseMetadata" in result:
            metadata = result["ResponseMetadata"]
            if "Error" in metadata:
                error = metadata["Error"]
                raise Exception(
                    f"API Error: {error.get('Code', 'Unknown')} - "
                    f"{error.get('Message', 'Unknown')}"
                )

        return result

    def _require_tos_config(self) -> None:
        missing = [
            name
            for name, value in [
                ("tos_bucket", self.tos_bucket),
                ("tos_region", self.tos_region),
                ("tos_endpoint", self.tos_endpoint),
            ]
            if not value
        ]
        if missing:
            raise ValueError(f"Missing TOS config: {', '.join(missing)}")

    def _tos_file_path(self, pod_id: str, phone_path: str) -> str:
        filename = phone_path.rstrip("/").rsplit("/", 1)[-1] or "download"
        return f"{self.tos_prefix.strip('/')}/{pod_id}/{filename}"

    def _json_request(
        self,
        action: str,
        version: Optional[str] = None,
        body: Optional[Dict[str, Any]] = None,
        method: str = "POST",
    ) -> Dict[str, Any]:
        path = "/"
        if version is None:
            version = self.ACTION_VERSIONS.get(action, self.version)
        if version is None:
            raise ValueError(f"Missing API version for action: {action}")

        query_params = {"Action": action, "Version": version}
        payload = self._serialize_payload(body or {})
        headers = self._sign_request(method, path, query_params, payload)
        headers["Content-Type"] = "application/json"
        result = self._send_http_request(
            method=method,
            path=path,
            headers=headers,
            query_params=query_params,
            body=payload.encode("utf-8"),
        )
        if "ResponseMetadata" in result:
            metadata = result["ResponseMetadata"]
            if "Error" in metadata:
                error = metadata["Error"]
                raise Exception(
                    f"API Error: {error.get('Code', 'Unknown')} - "
                    f"{error.get('Message', 'Unknown')}"
                )
        return result

    def _send_http_request(
        self,
        method: str,
        path: str,
        headers: Dict[str, str],
        query_params: Optional[Dict[str, Any]] = None,
        body: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        _, payload, response_headers = self._send_http_request_raw(
            method=method,
            path=path,
            headers=headers,
            query_params=query_params,
            body=body,
        )
        return self._decode_json_response(payload, response_headers)

    def _send_http_request_raw(
        self,
        method: str,
        path: str,
        headers: Dict[str, str],
        query_params: Optional[Dict[str, Any]] = None,
        body: Optional[bytes] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
    ) -> tuple[int, bytes, Any]:
        url = self.base_url + path
        if base_url is not None:
            url = base_url + path
        encoded_query = self._encode_query_params(query_params)
        if encoded_query:
            url = f"{url}?{encoded_query}"

        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(), exc.headers

    @staticmethod
    def _decode_json_response(payload: bytes, headers: Any) -> Dict[str, Any]:
        if not payload:
            return {}
        charset = headers.get_content_charset() or "utf-8"
        return json.loads(payload.decode(charset))

    @staticmethod
    def _decode_text_response(payload: bytes, headers: Any) -> str:
        if not payload:
            return ""
        charset = "utf-8"
        if headers is not None and hasattr(headers, "get_content_charset"):
            charset = headers.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")

    def _edge_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[bytes] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        parsed = urllib.parse.urlsplit(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path or "/"
        query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query_params = {key: value for key, value in query_pairs}
        status, payload, response_headers = self._send_http_request_raw(
            method=method,
            path=path,
            headers=headers or {},
            query_params=query_params,
            body=body,
            base_url=base_url,
            timeout=timeout,
        )
        text = self._decode_text_response(payload, response_headers)
        json_payload = None
        if text:
            try:
                json_payload = json.loads(text)
            except json.JSONDecodeError:
                json_payload = None
        return {
            "status": status,
            "body": payload,
            "text": text,
            "json": json_payload,
            "headers": response_headers,
        }

    @staticmethod
    def _extract_presigned_edge_url(payload: Any) -> str:
        preferred_keys = {
            "presignededgeurl",
            "presignedurl",
            "edgeurl",
            "url",
        }

        def walk(node: Any) -> Optional[str]:
            if isinstance(node, dict):
                for key, value in node.items():
                    if (
                        key.lower() in preferred_keys
                        and isinstance(value, str)
                        and value.startswith(("http://", "https://"))
                    ):
                        return value
                for value in node.values():
                    found = walk(value)
                    if found:
                        return found
            elif isinstance(node, list):
                for value in node:
                    found = walk(value)
                    if found:
                        return found
            return None

        url = walk(payload)
        if not url:
            raise ValueError("GetPreSignedEdgeURL response missing pre-signed URL")
        return url

    @staticmethod
    def _mask_presigned_edge_url(url: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    @staticmethod
    def _json_body_hash(body: Dict[str, Any]) -> str:
        payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _coerce_local_file_path(file_path: str) -> str:
        if file_path.startswith("file://"):
            return urllib.parse.unquote(urllib.parse.urlsplit(file_path).path)
        scheme = urllib.parse.urlsplit(file_path).scheme
        if scheme in {"http", "https"}:
            raise ValueError(
                "PushFile edge mode requires a local file path, not an HTTP URL"
            )
        return file_path

    @staticmethod
    def _resolve_phone_file_path(phone_path: str, local_path: str) -> str:
        normalized = phone_path.strip()
        if not normalized:
            raise ValueError("phone_path is required")
        if normalized.endswith("/"):
            return normalized.rstrip("/") + "/" + os.path.basename(local_path)
        basename = normalized.rsplit("/", 1)[-1]
        if "." not in basename:
            return normalized.rstrip("/") + "/" + os.path.basename(local_path)
        return normalized

    @staticmethod
    def _normalize_edge_sync_command_result(payload: Dict[str, Any]) -> Dict[str, Any]:
        if "Result" in payload and isinstance(payload.get("Result"), dict):
            payload.setdefault("Mode", "PreSignedEdgeURL")
            payload.setdefault("ResponseMetadata", {"Action": "RunSyncCommand"})
            return payload

        stdout = payload.get("Stdout")
        stderr = payload.get("Stderr")
        success = payload.get("Success")
        detail = stdout if success else (stderr or stdout)
        status = {
            "Success": success,
            "ExitCode": payload.get("ExitCode"),
            "TimedOut": payload.get("TimedOut"),
            "Stdout": stdout,
            "Stderr": stderr,
            "Detail": detail,
        }
        return {
            "Mode": "PreSignedEdgeURL",
            "ResponseMetadata": {"Action": "RunSyncCommand"},
            "Result": {
                "Status": [status],
                "EdgeResult": payload,
            },
        }

    # ========== 实例管理 ==========

    def create_pod(
        self,
        name: str,
        template_id: str,
        configuration_code: str,
        count: int = 1,
        product_id: Optional[str] = None,
        dc_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        创建云手机实例

        Args:
            name: 实例名称
            template_id: 机型模板 ID
            configuration_code: 套餐代码
            count: 创建数量，默认 1
            product_id: 产品 ID（可选，默认使用初始化时的值）
            dc_id: 机房 ID（可选，调用时按需要或资源余量指定）
            **kwargs: 其他参数

        Returns:
            创建结果
        """
        body = {"ProductId": product_id or self.product_id, **kwargs}
        if count == 1:
            body.update(
                {
                    "PodName": name,
                    "ConfigurationCode": configuration_code,
                }
            )
            if template_id and "PhoneTemplateId" not in body:
                body["PhoneTemplateId"] = template_id
        else:
            pod_spec = {
                "ApplyNum": count,
                "PodName": name,
                "ConfigurationCode": configuration_code,
            }
            if template_id and "PhoneTemplateId" not in body:
                pod_spec["PhoneTemplateId"] = template_id
            pod_spec_keys = {
                "PodName",
                "ImageId",
                "ConfigurationCode",
                "DataSize",
                "Dc",
                "DisplayLayoutId",
                "OverlaySettings",
                "OverlayProperty",
                "OverlayPersistProperty",
                "Start",
                "TagId",
                "UpBandwidthLimit",
                "DownBandwidthLimit",
                "CustomRouteId",
                "DNSId",
                "PortMappingRuleIdList",
                "IPWhiteList",
                "HostId",
                "PhoneTemplateId",
                "IsSelinuxOn",
            }
            for key in list(body):
                if key in pod_spec_keys:
                    pod_spec[key] = body.pop(key)
            body["PodSpecList"] = [pod_spec]
        if dc_id:
            target = body["PodSpecList"][0] if "PodSpecList" in body else body
            target["Dc"] = dc_id
        if "ResourceType" not in body and self.resource_type is not None:
            body["ResourceType"] = self.resource_type
        return self._request("CreatePod", body=body)

    def list_pods(
        self,
        page_size: Optional[int] = None,
        page_number: Optional[int] = None,
        product_id: Optional[str] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        查询云手机实例列表

        Args:
            page_size: 每页数量
            page_number: 页码
            product_id: 产品 ID（可选，默认使用初始化时的值）
            **kwargs: 其他过滤条件

        Returns:
            实例列表
        """
        if product_id is None:
            product_id = kwargs.pop("ProductId", self.product_id)
        else:
            kwargs.pop("ProductId", None)
        if max_results is None:
            max_results = kwargs.pop("MaxResults", None)
        else:
            kwargs.pop("MaxResults", None)
        if next_token is None:
            next_token = kwargs.pop("NextToken", None)
        else:
            kwargs.pop("NextToken", None)
        if page_number is None:
            page_number = kwargs.pop("PageNumber", None)
        else:
            kwargs.pop("PageNumber", None)

        body = self.compact_body(
            ProductId=product_id,
            MaxResults=max_results if max_results is not None else page_size,
            NextToken=next_token,
            PageNumber=page_number,
            **kwargs,
        )
        return self._request("ListPod", body=body)

    def detail_pod(
        self, pod_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = {
            "ProductId": product_id or kwargs.pop("ProductId", self.product_id),
            "PodId": pod_id,
            **kwargs,
        }
        return self._json_request("DetailPod", body=body)

    def delete_pod(
        self, pod_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = {
            "ProductId": product_id or kwargs.pop("ProductId", self.product_id),
            "PodIdList": kwargs.pop("PodIdList", [pod_id]),
            **kwargs,
        }
        return self._json_request("DeletePod", body=body)

    def update_pod(
        self,
        pod_id: str,
        product_id: Optional[str] = None,
        image_id: Optional[str] = None,
        force: Optional[bool] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodIdList=kwargs.pop("PodIdList", [pod_id]),
            ImageId=image_id or kwargs.pop("ImageId", None),
            Force=force,
            **kwargs,
        )
        return self._json_request("UpdatePod", body=body)

    def power_on_pod(
        self, pod_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = {
            "ProductId": product_id or kwargs.pop("ProductId", self.product_id),
            "PodIdList": kwargs.pop("PodIdList", [pod_id]),
            **kwargs,
        }
        return self._json_request("PowerOnPod", body=body)

    def power_off_pod(
        self, pod_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = {
            "ProductId": product_id or kwargs.pop("ProductId", self.product_id),
            "PodIdList": kwargs.pop("PodIdList", [pod_id]),
            **kwargs,
        }
        return self._json_request("PowerOffPod", body=body)

    def reboot_pod(
        self, pod_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = {
            "ProductId": product_id or kwargs.pop("ProductId", self.product_id),
            "PodIdList": kwargs.pop("PodIdList", [pod_id]),
            **kwargs,
        }
        return self._json_request("RebootPod", body=body)

    def reset_pod(
        self, pod_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = {
            "ProductId": product_id or kwargs.pop("ProductId", self.product_id),
            "PodIdList": kwargs.pop("PodIdList", [pod_id]),
            **kwargs,
        }
        return self._json_request("ResetPod", body=body)

    def create_pod_one_step(
        self,
        configuration_code: str,
        dc: str,
        app_list: list[Dict[str, Any]],
        *,
        product_id: Optional[str] = None,
        pod_name: Optional[str] = None,
        image_id: Optional[str] = None,
        data_size: Optional[str] = None,
        display_layout_id: Optional[str] = None,
        overlay_settings: Optional[list[Dict[str, Any]]] = None,
        overlay_property: Optional[list[Dict[str, Any]]] = None,
        overlay_persist_property: Optional[list[Dict[str, Any]]] = None,
        tag_id: Optional[str] = None,
        up_bandwidth_limit: Optional[int] = None,
        down_bandwidth_limit: Optional[int] = None,
        custom_route_id: Optional[str] = None,
        dns_id: Optional[str] = None,
        port_mapping_rule_id_list: Optional[list[str]] = None,
        ip_white_list: Optional[str] = None,
        resource_type: Optional[int] = None,
        host_id: Optional[str] = None,
        is_preinstall: Optional[bool] = None,
        use_phone_template: Optional[int] = None,
        phone_template_id: Optional[str] = None,
        is_selinux_on: Optional[bool] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodName=pod_name,
            ImageId=image_id,
            ConfigurationCode=configuration_code,
            DataSize=data_size,
            Dc=dc,
            DisplayLayoutId=display_layout_id,
            OverlaySettings=overlay_settings,
            OverlayProperty=overlay_property,
            OverlayPersistProperty=overlay_persist_property,
            TagId=tag_id,
            UpBandwidthLimit=up_bandwidth_limit,
            DownBandwidthLimit=down_bandwidth_limit,
            AppList=app_list,
            CustomRouteId=custom_route_id,
            DNSId=dns_id,
            PortMappingRuleIdList=port_mapping_rule_id_list,
            IPWhiteList=ip_white_list,
            ResourceType=resource_type
            if resource_type is not None
            else self.resource_type,
            HostId=host_id,
            IsPreinstall=is_preinstall,
            UsePhoneTemplate=use_phone_template,
            PhoneTemplateId=phone_template_id,
            IsSelinuxOn=is_selinux_on,
            **kwargs,
        )
        return self._json_request("CreatePodOneStep", body=body)

    def update_pod_property(
        self,
        *,
        pod_id: Optional[str] = None,
        pod_id_list: Optional[list[str]] = None,
        pod_settings: Optional[list[Dict[str, Any]]] = None,
        pod_properties: Optional[list[Dict[str, Any]]] = None,
        pod_persist_properties: Optional[list[Dict[str, Any]]] = None,
        phone_template_id: Optional[str] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodId=pod_id,
            PodIdList=pod_id_list,
            PodSettings=pod_settings,
            PodProperties=pod_properties,
            PodPersistProperties=pod_persist_properties,
            PhoneTemplateId=phone_template_id,
            **kwargs,
        )
        return self._json_request("UpdatePodProperty", body=body)

    def update_pod_resource_apply_num(
        self,
        apply_num: int,
        *,
        resource_set_id: Optional[str] = None,
        configuration_code: Optional[str] = None,
        dc: Optional[str] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            ResourceSetId=resource_set_id,
            ConfigurationCode=configuration_code,
            Dc=dc,
            ApplyNum=apply_num,
            **kwargs,
        )
        return self._json_request("UpdatePodResourceApplyNum", body=body)

    def update_product_resource(
        self,
        apply_data_size: int,
        *,
        product_id: Optional[str] = None,
        volc_region: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            ApplyDataSize=apply_data_size,
            VolcRegion=volc_region,
            **kwargs,
        )
        return self._json_request("UpdateProductResource", body=body)

    def backup_pod(
        self, pod_id_list: list[str], *, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodIdList=pod_id_list,
            **kwargs,
        )
        return self._json_request("BackupPod", body=body)

    def cancel_backup_pod(
        self, pod_id_list: list[str], *, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodIdList=pod_id_list,
            **kwargs,
        )
        return self._json_request("CancelBackupPod", body=body)

    def restore_pod(
        self,
        *,
        pod_id_list: Optional[list[str]] = None,
        specify_host_list: Optional[list[Dict[str, Any]]] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodIdList=pod_id_list,
            SpecifyHostList=specify_host_list,
            **kwargs,
        )
        return self._json_request("RestorePod", body=body)

    def cancel_restore_pod(
        self, pod_id_list: list[str], *, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodIdList=pod_id_list,
            **kwargs,
        )
        return self._json_request("CancelRestorePod", body=body)

    def pod_data_transfer(
        self,
        origin_pod_id: str,
        dst_pod_id_list: list[str],
        *,
        transfer_type: Optional[int] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            OriginPodId=origin_pod_id,
            DstPodIdList=dst_pod_id_list,
            Type=transfer_type,
            **kwargs,
        )
        return self._json_request("PodDataTransfer", body=body)

    def pod_mute(
        self,
        pod_id: str,
        mute: bool,
        *,
        display_list: Optional[list[str]] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodId=pod_id,
            Mute=mute,
            DisplayList=display_list,
            **kwargs,
        )
        return self._json_request("PodMute", body=body)

    def pod_adb(
        self, pod_id: str, enable: bool, *, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodId=pod_id,
            Enable=enable,
            **kwargs,
        )
        return self._json_request("PodAdb", body=body)

    def pod_stop(
        self, pod_id: str, *, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodId=pod_id,
            **kwargs,
        )
        return self._json_request("PodStop", body=body)

    def pod_data_delete(
        self,
        pod_id: str,
        file_path_list: list[str],
        *,
        package_list: Optional[list[str]] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodId=pod_id,
            FilePathList=file_path_list,
            PackageList=package_list,
            **kwargs,
        )
        return self._json_request("PodDataDelete", body=body)

    def set_proxy(
        self,
        pod_id_list: list[str],
        proxy_status: int,
        *,
        proxy_config: Optional[Dict[str, Any]] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodIdList=pod_id_list,
            ProxyStatus=proxy_status,
            ProxyConfig=proxy_config,
            **kwargs,
        )
        return self._json_request("SetProxy", body=body)

    def get_proxy(
        self, pod_id_list: list[str], *, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodIdList=pod_id_list,
            **kwargs,
        )
        return self._json_request("GetProxy", body=body)

    def migrate_pod(
        self,
        pod_id_list: list[str],
        *,
        target_dc: Optional[str] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodIdList=pod_id_list,
            TargetDc=target_dc,
            **kwargs,
        )
        return self._json_request("MigratePod", body=body)

    def backup_data(
        self,
        pod_id_list: list[str],
        *,
        description: Optional[str] = None,
        backup_all: Optional[bool] = None,
        include_path_list: Optional[list[str]] = None,
        exclude_path_list: Optional[list[str]] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodIdList=pod_id_list,
            Description=description,
            BackupAll=backup_all,
            IncludePathList=include_path_list,
            ExcludePathList=exclude_path_list,
            **kwargs,
        )
        return self._json_request("BackupData", body=body)

    def restore_data(
        self,
        backup_data_id: str,
        *,
        pod_id_list: Optional[list[str]] = None,
        create_pod_num: Optional[int] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            BackupDataId=backup_data_id,
            PodIdList=pod_id_list,
            CreatePodNum=create_pod_num,
            **kwargs,
        )
        return self._json_request("RestoreData", body=body)

    def list_backup_data(
        self,
        *,
        source_pod_id: Optional[str] = None,
        backup_data_id_list: Optional[list[str]] = None,
        status: Optional[str] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            SourcePodId=source_pod_id,
            BackupDataIdList=backup_data_id_list,
            Status=status,
            MaxResults=max_results,
            NextToken=next_token,
            **kwargs,
        )
        return self._json_request("ListBackupData", body=body)

    def delete_backup_data(
        self,
        backup_data_id_list: list[str],
        *,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            BackupDataIdList=backup_data_id_list,
            **kwargs,
        )
        return self._json_request("DeleteBackupData", body=body)

    # ========== 应用管理 ==========

    def install_app(
        self, pod_id: str, app_id: str, version_id: str, **kwargs
    ) -> Dict[str, Any]:
        body = {
            "ProductId": kwargs.pop("ProductId", self.product_id),
            "PodIdList": kwargs.pop("PodIdList", [pod_id]),
            "AppId": app_id,
            "VersionId": version_id,
            **kwargs,
        }
        return self._json_request("InstallApp", body=body)

    def launch_app(self, pod_id: str, package_name: str, **kwargs) -> Dict[str, Any]:
        body = {
            "ProductId": kwargs.pop("ProductId", self.product_id),
            "PodIdList": kwargs.pop("PodIdList", [pod_id]),
            "PackageName": package_name,
            **kwargs,
        }
        return self._json_request("LaunchApp", body=body)

    def close_app(self, pod_id: str, package_name: str, **kwargs) -> Dict[str, Any]:
        body = {
            "ProductId": kwargs.pop("ProductId", self.product_id),
            "PodIdList": kwargs.pop("PodIdList", [pod_id]),
            "PackageName": package_name,
            **kwargs,
        }
        return self._json_request("CloseApp", body=body)

    def uninstall_app(self, pod_id: str, app_id: str, **kwargs) -> Dict[str, Any]:
        body = {
            "ProductId": kwargs.pop("ProductId", self.product_id),
            "PodIdList": kwargs.pop("PodIdList", [pod_id]),
            "AppId": app_id,
            **kwargs,
        }
        return self._json_request("UninstallApp", body=body)

    def auto_install_app(
        self,
        pod_id_list: list[str],
        *,
        install_type: Optional[int] = None,
        download_url: Optional[str] = None,
        package_name: Optional[str] = None,
        version_code: Optional[int] = None,
        image_id: Optional[str] = None,
        absolute_path: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=kwargs.pop("ProductId", self.product_id),
            PodIdList=pod_id_list,
            InstallType=install_type,
            DownloadURL=download_url,
            PackageName=package_name,
            VersionCode=version_code,
            ImageId=image_id,
            AbsolutePath=absolute_path,
            **kwargs,
        )
        return self._json_request("AutoInstallApp", body=body)

    def get_pod_app_list(self, pod_id: str, **kwargs) -> Dict[str, Any]:
        """
        获取实例应用列表

        Args:
            pod_id: 实例 ID

        Returns:
            应用列表
        """
        body = {
            "ProductId": kwargs.pop("ProductId", self.product_id),
            "PodId": pod_id,
            **kwargs,
        }
        return self._json_request("GetPodAppList", body=body)

    # ========== 云手机操控 ==========

    def start_recording(
        self,
        pod_id: str,
        duration_limit: int,
        round_id: str,
        *,
        product_id: Optional[str] = None,
        is_saved_on_pod: Optional[bool] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodId=pod_id,
            DurationLimit=duration_limit,
            RoundId=round_id,
            IsSavedOnPod=is_saved_on_pod,
            **kwargs,
        )
        return self._json_request("StartRecording", body=body)

    def stop_recording(self, pod_id: str, **kwargs) -> Dict[str, Any]:
        body = {
            "ProductId": kwargs.pop("ProductId", self.product_id),
            "PodId": pod_id,
            **kwargs,
        }
        return self._json_request("StopRecording", body=body)

    def batch_screen_shot(
        self,
        pod_id: str,
        *,
        product_id: Optional[str] = None,
        pod_id_list: Optional[List[str]] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        quality: Optional[int] = None,
        is_saved_on_pod: Optional[bool] = None,
        resize_mode: Optional[int] = None,
        rotation: Optional[int] = None,
        upload_type: Optional[int] = None,
        tos_info: Optional[Dict[str, Any]] = None,
        round_id: Optional[str] = None,
        is_broadcasted: Optional[bool] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """执行 BatchScreenShot 截图。"""
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodIdList=pod_id_list or kwargs.pop("PodIdList", [pod_id]),
            Width=width,
            Height=height,
            Quality=quality,
            IsSavedOnPod=is_saved_on_pod,
            ResizeMode=resize_mode,
            Rotation=rotation,
            UploadType=upload_type,
            TosInfo=tos_info,
            RoundId=round_id,
            IsBroadcasted=is_broadcasted,
            **kwargs,
        )
        return self._json_request("BatchScreenShot", body=body)

    def ban_user(
        self,
        *,
        pod_id: str,
        user_id: str,
        product_id: Optional[str] = None,
        forbidden_interval: Optional[int] = None,
        is_preview_stream: Optional[bool] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodId=pod_id,
            UserId=user_id,
            ForbiddenInterval=forbidden_interval,
            IsPreviewStream=is_preview_stream,
            **kwargs,
        )
        return self._json_request("BanUser", body=body)

    def start_screenshot(self, pod_id: str, **kwargs) -> Dict[str, Any]:
        """兼容旧调用，内部复用 BatchScreenShot。"""
        return self.batch_screen_shot(pod_id, **kwargs)

    def stop_screenshot(self, pod_id: str, **kwargs) -> Dict[str, Any]:
        body = {
            "ProductId": kwargs.pop("ProductId", self.product_id),
            "PodIdList": kwargs.pop("PodIdList", [pod_id]),
            **kwargs,
        }
        return self._json_request("StopScreenShot", body=body)

    def get_presigned_edge_url(
        self,
        pod_id: str,
        api_type: str,
        api_payload: Optional[Dict[str, Any]] = None,
        api_path: Optional[str] = None,
        ttl: Optional[int] = 60,
        timeout: Optional[int] = None,
        single_use: Optional[bool] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        payload = None
        if api_payload is not None:
            payload = {
                str(key): (
                    "true"
                    if value is True
                    else "false"
                    if value is False
                    else str(value)
                )
                for key, value in api_payload.items()
            }
        if product_id is None:
            product_id = kwargs.pop("ProductId", self.product_id)
        else:
            kwargs.pop("ProductId", None)
        if ttl is None:
            ttl = 60
        body = self.compact_body(
            ProductId=product_id,
            PodId=pod_id,
            APIType=api_type,
            APIPayload=payload,
            APIPath=api_path,
            TTL=ttl,
            Timeout=timeout,
            SingleUse=single_use,
            **kwargs,
        )
        return self._json_request("GetPreSignedEdgeURL", body=body)

    def push_file(
        self, pod_id: str, file_url: str, phone_path: str, **kwargs
    ) -> Dict[str, Any]:
        product_id = kwargs.pop("ProductId", self.product_id)
        overwrite = kwargs.pop("OverWrite", kwargs.pop("Overwrite", None))
        auto_unzip = kwargs.pop("AutoUnzip", None)
        ttl = kwargs.pop("TTL", None)
        timeout = kwargs.pop("Timeout", None)
        single_use = kwargs.pop("SingleUse", None)
        local_path = self._coerce_local_file_path(file_url)
        resolved_phone_path = self._resolve_phone_file_path(phone_path, local_path)
        with open(local_path, "rb") as file_obj:
            content = file_obj.read()
        edge_info = self.get_presigned_edge_url(
            pod_id,
            api_type="UploadFile",
            api_payload=self.compact_body(
                Path=resolved_phone_path,
                OverWrite=overwrite,
                AutoUnzip=auto_unzip,
            ),
            ttl=ttl,
            timeout=timeout,
            single_use=single_use,
            product_id=product_id,
            APIBodyHash="UNSIGNED-PAYLOAD",
            **kwargs,
        )
        edge_url = self._extract_presigned_edge_url(edge_info)
        response = self._edge_request(
            "PUT",
            edge_url,
            headers={"Content-Type": "application/octet-stream"},
            body=content,
            timeout=timeout or 30,
        )
        if response["status"] not in {200, 201, 204}:
            raise Exception(
                f"PushFile edge upload failed: HTTP {response['status']} - {response['text']}"
            )
        result = {
            "Mode": "PreSignedEdgeURL",
            "ResponseMetadata": {"Action": "PushFile"},
            "Result": {
                "LocalPath": os.path.abspath(local_path),
                "PhonePath": resolved_phone_path,
                "BytesWritten": len(content),
                "HTTPStatusCode": response["status"],
                "EdgeURL": self._mask_presigned_edge_url(edge_url),
            },
        }
        if response["json"] is not None:
            result["Result"]["EdgeResponse"] = response["json"]
        elif response["text"]:
            result["Result"]["EdgeResponseText"] = response["text"]
        return result

    def pull_file(
        self, pod_id: str, phone_path: str, output_path: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        product_id = kwargs.pop("ProductId", self.product_id)
        range_header = kwargs.pop("Range", None)
        ttl = kwargs.pop("TTL", None)
        timeout = kwargs.pop("Timeout", None)
        single_use = kwargs.pop("SingleUse", None)
        edge_info = self.get_presigned_edge_url(
            pod_id,
            api_type="DownloadFile",
            api_payload={"Path": phone_path},
            ttl=ttl,
            timeout=timeout,
            single_use=single_use,
            product_id=product_id,
            **kwargs,
        )
        edge_url = self._extract_presigned_edge_url(edge_info)
        headers = {}
        if range_header is not None:
            headers["Range"] = range_header
        response = self._edge_request(
            "GET",
            edge_url,
            headers=headers,
            timeout=timeout or 30,
        )
        if response["status"] not in {200, 206}:
            raise Exception(
                f"PullFile edge download failed: HTTP {response['status']} - {response['text']}"
            )
        if output_path is None:
            filename = phone_path.rstrip("/").rsplit("/", 1)[-1] or "download"
            output_path = os.path.abspath(filename)
        else:
            output_path = os.path.abspath(output_path)
        with open(output_path, "wb") as file_obj:
            file_obj.write(response["body"])
        return {
            "Mode": "PreSignedEdgeURL",
            "ResponseMetadata": {"Action": "PullFile"},
            "Result": {
                "PhonePath": phone_path,
                "LocalPath": output_path,
                "BytesWritten": len(response["body"]),
                "HTTPStatusCode": response["status"],
                "Range": range_header,
                "EdgeURL": self._mask_presigned_edge_url(edge_url),
            },
        }

    def run_command(
        self,
        pod_id: str,
        command: str,
        *,
        product_id: Optional[str] = None,
        pod_id_list: Optional[List[str]] = None,
        permission_type: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodIdList=pod_id_list or kwargs.pop("PodIdList", [pod_id]),
            Command=command,
            PermissionType=permission_type,
            TimeoutSeconds=timeout_seconds,
            **kwargs,
        )
        return self._json_request("RunCommand", body=body)

    def run_sync_command(self, pod_id: str, command: str, **kwargs) -> Dict[str, Any]:
        product_id = kwargs.pop("ProductId", self.product_id)
        edge_timeout = kwargs.get("TimeoutSecond")
        body = self.compact_body(
            Command=command,
            PermissionType=kwargs.pop("PermissionType", None),
            TimeoutSecond=kwargs.pop("TimeoutSecond", None),
            ResultLength=kwargs.pop("ResultLength", None),
            **kwargs,
        )
        try:
            edge_info = self.get_presigned_edge_url(
                pod_id,
                api_type="RunSyncCommand",
                timeout=edge_timeout,
                product_id=product_id,
                APIBodyHash=self._json_body_hash(body),
            )
            edge_url = self._extract_presigned_edge_url(edge_info)
            response = self._edge_request(
                "POST",
                edge_url,
                headers={"Content-Type": "application/json;charset=utf-8"},
                body=json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode(
                    "utf-8"
                ),
                timeout=edge_timeout or 30,
            )
            if response["status"] >= 400:
                raise Exception(
                    f"RunSyncCommand edge request failed: HTTP {response['status']} - {response['text']}"
                )
            if not isinstance(response["json"], dict):
                raise Exception("RunSyncCommand edge response is not valid JSON")
            result = self._normalize_edge_sync_command_result(response["json"])
            result["Result"]["EdgeURL"] = self._mask_presigned_edge_url(edge_url)
            return result
        except Exception:
            fallback_body = {
                "ProductId": product_id,
                "PodIdList": [pod_id],
                "Command": command,
                **body,
            }
            result = self._json_request("RunSyncCommand", body=fallback_body)
            result["Mode"] = "OpenAPIFallback"
            return result

    # ========== 镜像管理 ==========

    def list_aosp_images(
        self,
        product_id: Optional[str] = None,
        image_id_list: Optional[List[str]] = None,
        image_name: Optional[str] = None,
        aosp_version: Optional[str] = None,
        is_public: Optional[bool] = None,
        image_status: Optional[int] = None,
        expand_scope: Optional[bool] = None,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None,
        page_size: Optional[int] = None,
        page_number: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            ImageIdList=image_id_list,
            ImageName=image_name,
            AOSPVersion=aosp_version,
            IsPublic=is_public,
            ImageStatus=image_status,
            ExpandScope=expand_scope,
            MaxResults=max_results if max_results is not None else page_size,
            NextToken=next_token,
            PageNumber=page_number,
            **kwargs,
        )
        return self._json_request("ListAOSPImage", body=body)

    def delete_aosp_image(
        self, *, image_id_list: List[str], product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            ImageIdList=image_id_list,
            **kwargs,
        )
        return self._json_request("DeleteAOSPImage", body=body)

    def update_aosp_image(
        self,
        *,
        image_id: str,
        product_id: Optional[str] = None,
        image_name: Optional[str] = None,
        image_annotation: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            ImageId=image_id,
            ImageName=image_name,
            ImageAnnotation=image_annotation,
            **kwargs,
        )
        return self._json_request("UpdateAOSPImage", body=body)

    def create_image_one_step(
        self,
        *,
        image_id: str,
        product_id: Optional[str] = None,
        image_name: Optional[str] = None,
        image_annotation: Optional[str] = None,
        file_url: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            ImageId=image_id,
            ImageName=image_name,
            ImageAnnotation=image_annotation,
            FileURL=file_url,
            **kwargs,
        )
        return self._json_request("CreateImageOneStep", body=body)

    def build_aosp_image(
        self,
        *,
        product_id: Optional[str] = None,
        image_name: Optional[str] = None,
        image_annotation: Optional[str] = None,
        image_file_format: Optional[str] = None,
        system_url: Optional[str] = None,
        vendor_url: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            ImageName=image_name,
            ImageAnnotation=image_annotation,
            ImageFileFormat=image_file_format,
            SystemURL=system_url,
            VendorURL=vendor_url,
            **kwargs,
        )
        return self._json_request("BuildAOSPImage", body=body)

    # ========== 资源管理 ==========

    def list_pod_resources(
        self,
        offset: int = 0,
        count: int = 10,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self.request_action(
            "ListPodResource",
            ProductId=product_id or self.product_id,
            Offset=offset,
            Count=count,
            **kwargs,
        )

    def list_pod_resource_set(
        self,
        offset: int = 0,
        count: int = 10,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self.request_action(
            "ListPodResourceSet",
            json_body=False,
            ProductId=product_id or self.product_id,
            Offset=offset,
            Count=count,
            **kwargs,
        )

    def get_product_resource(
        self, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = {"ProductId": product_id or self.product_id, **kwargs}
        return self._request("GetProductResource", body=body)

    def list_products(
        self,
        product_id: Optional[str] = None,
        product_name: Optional[str] = None,
        cloudphone_product_type: int = 5,
        resource_type: Optional[int] = None,
        cloudphone_product_use_type: Optional[int] = None,
        offset: Optional[int] = None,
        count: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self.request_action(
            "ListOperableProduct",
            json_body=True,
            ProductId=product_id,
            ProductName=product_name,
            CloudphoneProductType=cloudphone_product_type,
            ResourceType=resource_type,
            CloudphoneProductUseType=cloudphone_product_use_type,
            Offset=offset,
            Count=count,
            **kwargs,
        )

    def list_configurations(
        self,
        offset: int = 0,
        count: int = 10,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self.request_action(
            "ListConfiguration",
            ProductId=product_id or self.product_id,
            Offset=offset,
            Count=count,
            **kwargs,
        )

    def list_phone_templates(
        self,
        max_results: int = 10,
        next_token: Optional[str] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self.request_action(
            "ListPhoneTemplate",
            json_body=True,
            ProductId=product_id or self.product_id,
            MaxResults=max_results,
            NextToken=next_token,
            **kwargs,
        )

    def subscribe_resource_auto(self, **kwargs) -> Dict[str, Any]:
        product_id = kwargs.pop("ProductId", self.product_id)
        if "PreOrderList" not in kwargs:
            resource_type = kwargs.pop("ResourceType", self.resource_type)
            configuration_code = kwargs.pop("ConfigurationCode", None)
            if int(resource_type) == 200 and not configuration_code:
                raise ValueError(
                    "ConfigurationCode is required for local-storage SubscribeResourceAuto"
                )
            pre_order = self.compact_body(
                ProductId=product_id,
                ConfigurationCode=configuration_code,
                ServerTypeCode=kwargs.pop("ServerTypeCode", None),
                Dc=kwargs.pop("Dc", None),
                ApplyNum=kwargs.pop("ApplyNum", None),
                ResourceType=resource_type,
                ChargeType=kwargs.pop("ChargeType", None),
                Term=kwargs.pop("Term", None),
                Period=kwargs.pop("Period", None),
                Region=kwargs.pop("Region", None),
                VolcRegion=kwargs.pop("VolcRegion", None),
                AutoCreatePod=kwargs.pop("AutoCreatePod", None),
                ImageId=kwargs.pop("ImageId", None),
                DisplayLayoutId=kwargs.pop("DisplayLayoutId", None),
            )
            kwargs["PreOrderList"] = [pre_order]
        return self._json_request(
            "SubscribeResourceAuto", body={"ProductId": product_id, **kwargs}
        )

    def renew_resource_auto(self, **kwargs) -> Dict[str, Any]:
        return self._json_request(
            "RenewResourceAuto",
            body={"ProductId": kwargs.pop("ProductId", self.product_id), **kwargs},
        )

    def unsubscribe_host_resource(
        self,
        host_id_list: List[str],
        force: Optional[bool] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self._json_request(
            "UnsubscribeHostResource",
            body=self.compact_body(
                ProductId=product_id or kwargs.pop("ProductId", self.product_id),
                HostIdList=host_id_list,
                Force=force,
                **kwargs,
            ),
        )

    def list_instance_configuration_specs(
        self, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        return self.request_action(
            "ListInstanceConfigurationSpec",
            ProductId=product_id or self.product_id,
            **kwargs,
        )

    # ========== 只读扩展接口 ==========

    def get_task_info(
        self, task_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        return self.request_action(
            "GetTaskInfo",
            json_body=True,
            ProductId=product_id or self.product_id,
            TaskId=task_id,
            **kwargs,
        )

    def list_tasks(
        self,
        max_results: int = 10,
        next_token: Optional[str] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self.request_action(
            "ListTask",
            ProductId=product_id or self.product_id,
            MaxResults=max_results,
            NextToken=next_token,
            **kwargs,
        )

    def get_pod_metric(
        self, pod_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        return self.request_action(
            "GetPodMetric",
            json_body=True,
            ProductId=product_id or self.product_id,
            PodId=pod_id,
            **kwargs,
        )

    def get_pod_property(
        self, pod_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        return self.request_action(
            "GetPodProperty",
            json_body=True,
            ProductId=product_id or self.product_id,
            PodId=pod_id,
            **kwargs,
        )

    def get_phone_template(
        self, phone_template_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        return self.request_action(
            "GetPhoneTemplate",
            ProductId=product_id or self.product_id,
            PhoneTemplateId=phone_template_id,
            **kwargs,
        )

    def add_phone_template(
        self,
        phone_template_name: str,
        aosp_version: str,
        status: int,
        *,
        overlay_property: Optional[list[Dict[str, Any]]] = None,
        overlay_persist_property: Optional[list[Dict[str, Any]]] = None,
        overlay_settings: Optional[list[Dict[str, Any]]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            PhoneTemplateName=phone_template_name,
            OverlayProperty=overlay_property,
            OverlayPersistProperty=overlay_persist_property,
            OverlaySettings=overlay_settings,
            AospVersion=aosp_version,
            Status=status,
            **kwargs,
        )
        return self._json_request("AddPhoneTemplate", body=body)

    def update_phone_template(
        self,
        phone_template_id: str,
        *,
        phone_template_name: Optional[str] = None,
        status: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            PhoneTemplateId=phone_template_id,
            PhoneTemplateName=phone_template_name,
            Status=status,
            **kwargs,
        )
        return self._json_request("UpdatePhoneTemplate", body=body)

    def remove_phone_template(self, phone_template_id: str, **kwargs) -> Dict[str, Any]:
        body = self.compact_body(PhoneTemplateId=phone_template_id, **kwargs)
        return self._json_request("RemovePhoneTemplate", body=body)

    def list_hosts(
        self,
        max_results: int = 10,
        next_token: Optional[str] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self.request_action(
            "ListHost",
            json_body=True,
            ProductId=product_id or self.product_id,
            MaxResults=max_results,
            NextToken=next_token,
            **kwargs,
        )

    def detail_host(
        self, host_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        return self.request_action(
            "DetailHost",
            ProductId=product_id or self.product_id,
            HostId=host_id,
            **kwargs,
        )

    def update_host(
        self,
        host_id_list: List[str],
        configuration_code: Optional[str] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self._json_request(
            "UpdateHost",
            body=self.compact_body(
                ProductId=product_id or kwargs.pop("ProductId", self.product_id),
                HostIdList=host_id_list,
                ConfigurationCode=configuration_code,
                **kwargs,
            ),
        )

    def reboot_host(
        self,
        host_id_list: List[str],
        force: Optional[bool] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self._json_request(
            "RebootHost",
            body=self.compact_body(
                ProductId=product_id or kwargs.pop("ProductId", self.product_id),
                HostIdList=host_id_list,
                Force=force,
                **kwargs,
            ),
        )

    def reset_host(
        self,
        host_id_list: List[str],
        force: Optional[bool] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self._json_request(
            "ResetHost",
            body=self.compact_body(
                ProductId=product_id or kwargs.pop("ProductId", self.product_id),
                HostIdList=host_id_list,
                Force=force,
                **kwargs,
            ),
        )

    def list_image_resources(
        self,
        offset: int = 0,
        count: int = 10,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self.request_action(
            "ListImageResource",
            ProductId=product_id or self.product_id,
            Offset=offset,
            Count=count,
            **kwargs,
        )

    def get_image_preheating(
        self,
        image_id_list: List[str],
        product_id: Optional[str] = None,
        dc_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self.request_action(
            "GetImagePreheating",
            ProductId=product_id or self.product_id,
            ImageIdList=",".join(image_id_list),
            DcId=dc_id,
            **kwargs,
        )

    def get_dc_bandwidth_daily_peak(
        self, dc_id_list: list[str], product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        normalized_dc_id_list = dc_id_list
        if len(dc_id_list) == 1 and isinstance(dc_id_list[0], list):
            normalized_dc_id_list = dc_id_list[0]
        body = self.compact_body(
            ProductId=product_id or self.product_id,
            DcIdList=normalized_dc_id_list,
            **kwargs,
        )
        return self._json_request("GetDcBandwidthDailyPeak", body=body)

    def list_display_layouts(
        self,
        offset: int = 0,
        count: int = 10,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self.request_action(
            "ListDisplayLayoutMini",
            ProductId=product_id or self.product_id,
            Offset=offset,
            Count=count,
            **kwargs,
        )

    def detail_display_layout(
        self, display_layout_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        return self.request_action(
            "DetailDisplayLayoutMini",
            ProductId=product_id or self.product_id,
            DisplayLayoutId=display_layout_id,
            **kwargs,
        )

    def create_display_layout(
        self,
        *,
        display_layout_id: str,
        width: int,
        height: int,
        product_id: Optional[str] = None,
        density: Optional[int] = None,
        fps: Optional[int] = None,
        extra: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            DisplayLayoutId=display_layout_id,
            Width=width,
            Height=height,
            Density=density,
            Fps=fps,
            Extra=extra,
            **kwargs,
        )
        return self._json_request("CreateDisplayLayoutMini", body=body)

    def delete_display_layout(
        self, *, display_layout_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            DisplayLayoutId=display_layout_id,
            **kwargs,
        )
        return self._json_request("DeleteDisplayLayout", body=body)

    def detail_app(
        self, app_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        return self.request_action(
            "DetailApp", ProductId=product_id or self.product_id, AppId=app_id, **kwargs
        )

    def install_apps(
        self,
        *,
        pod_id: str,
        app_list: List[Dict[str, Any]],
        product_id: Optional[str] = None,
        install_type: Optional[int] = None,
        is_preinstall: Optional[bool] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or self.product_id,
            PodId=pod_id,
            AppList=app_list,
            InstallType=install_type,
            IsPreinstall=is_preinstall,
            **kwargs,
        )
        return self._json_request("InstallApps", body=body)

    def upload_app(
        self,
        *,
        app_type: int,
        download_url: str,
        product_id: Optional[str] = None,
        app_id: Optional[str] = None,
        app_name: Optional[str] = None,
        rotation: Optional[int] = None,
        app_desc: Optional[str] = None,
        parse_flag: Optional[int] = None,
        app_mode: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or self.product_id,
            AppType=app_type,
            DownloadUrl=download_url,
            AppId=app_id,
            AppName=app_name,
            Rotation=rotation,
            AppDesc=app_desc,
            ParseFlag=parse_flag,
            AppMode=app_mode,
            **kwargs,
        )
        return self._json_request("UploadApp", body=body)

    def update_app(
        self,
        *,
        app_id: str,
        product_id: Optional[str] = None,
        app_name: Optional[str] = None,
        rotation: Optional[int] = None,
        icon_url: Optional[str] = None,
        app_desc: Optional[str] = None,
        app_mode: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or self.product_id,
            AppId=app_id,
            AppName=app_name,
            Rotation=rotation,
            IconUrl=icon_url,
            AppDesc=app_desc,
            AppMode=app_mode,
            **kwargs,
        )
        return self._json_request("UpdateApp", body=body)

    def delete_app(
        self, *, app_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or self.product_id, AppId=app_id, **kwargs
        )
        return self._json_request("DeleteApp", body=body)

    def delete_app_version(
        self, *, version_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or self.product_id, VersionId=version_id, **kwargs
        )
        return self._json_request("DeleteAppVersion", body=body)

    def launch_apps(
        self,
        *,
        pod_id: str,
        package_name_list: List[str],
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or self.product_id,
            PodId=pod_id,
            PackageNameList=package_name_list,
            **kwargs,
        )
        return self._json_request("LaunchApps", body=body)

    def list_apps(
        self,
        max_results: int = 10,
        next_token: Optional[str] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self.request_action(
            "ListApp",
            json_body=True,
            ProductId=product_id or self.product_id,
            MaxResults=max_results,
            NextToken=next_token,
            **kwargs,
        )

    def list_app_version_deploys(
        self, app_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        return self.request_action(
            "ListAppVersionDeploy",
            ProductId=product_id or self.product_id,
            AppId=app_id,
            **kwargs,
        )

    def get_app_crash_log(
        self,
        pod_id_list,
        start_time: int,
        end_time: int,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        pod_id_value = (
            ",".join(pod_id_list) if isinstance(pod_id_list, list) else pod_id_list
        )
        return self.request_action(
            "GetAppCrashLog",
            ProductId=product_id or self.product_id,
            PodIdList=pod_id_value,
            StartTime=start_time,
            EndTime=end_time,
            **kwargs,
        )

    def list_tags(
        self,
        offset: int = 0,
        count: int = 10,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self.request_action(
            "ListTag",
            ProductId=product_id or self.product_id,
            Offset=offset,
            Count=count,
            **kwargs,
        )

    def create_tag(
        self,
        tag_name: str,
        product_id: Optional[str] = None,
        tag_desc: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or self.product_id,
            TagName=tag_name,
            TagDesc=tag_desc,
            **kwargs,
        )
        return self._json_request("CreateTag", body=body)

    def update_tag(
        self,
        tag_id: str,
        product_id: Optional[str] = None,
        tag_name: Optional[str] = None,
        tag_desc: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or self.product_id,
            TagId=tag_id,
            TagName=tag_name,
            TagDesc=tag_desc,
            **kwargs,
        )
        return self._json_request("UpdateTag", body=body)

    def delete_tag(
        self, tag_id_list: List[str], product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or self.product_id,
            TagIdList=tag_id_list,
            **kwargs,
        )
        return self._json_request("DeleteTag", body=body)

    def attach_tag(
        self,
        tag_id: str,
        pod_id_list: List[str],
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or self.product_id,
            TagId=tag_id,
            PodIdList=pod_id_list,
            **kwargs,
        )
        return self._json_request("AttachTag", body=body)

    def list_port_mapping_rules(
        self,
        offset: int = 0,
        count: int = 10,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self.request_action(
            "ListPortMappingRule",
            ProductId=product_id or self.product_id,
            Offset=offset,
            Count=count,
            **kwargs,
        )

    def detail_port_mapping_rule(
        self, port_mapping_rule_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        return self.request_action(
            "DetailPortMappingRule",
            ProductId=product_id or self.product_id,
            PortMappingRuleId=port_mapping_rule_id,
            **kwargs,
        )

    def create_port_mapping_rule(
        self,
        *,
        source_port: int,
        product_id: Optional[str] = None,
        port_mapping_rule_id: Optional[str] = None,
        protocol: Optional[str] = None,
        isp: Optional[int] = None,
        direction: Optional[str] = None,
        volc_region: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PortMappingRuleId=port_mapping_rule_id,
            Protocol=protocol,
            SourcePort=source_port,
            ISP=isp,
            Direction=direction,
            VolcRegion=volc_region,
            **kwargs,
        )
        return self._json_request("CreatePortMappingRule", body=body)

    def bind_port_mapping_rule(
        self,
        *,
        pod_id_list: list[str],
        port_mapping_rule_id_list: list[str],
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodIdList=pod_id_list,
            PortMappingRuleIdList=port_mapping_rule_id_list,
            **kwargs,
        )
        return self._json_request("BindPortMappingRule", body=body)

    def unbind_port_mapping_rule(
        self,
        *,
        pod_id_list: list[str],
        port_mapping_rule_id_list: list[str],
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            PodIdList=pod_id_list,
            PortMappingRuleIdList=port_mapping_rule_id_list,
            **kwargs,
        )
        return self._json_request("UnbindPortMappingRule", body=body)

    def list_dns_rules(
        self,
        offset: int = 0,
        count: int = 10,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self.request_action(
            "ListDNSRule",
            json_body=True,
            ProductId=product_id or self.product_id,
            Offset=offset,
            Count=count,
            **kwargs,
        )

    def detail_dns_rule(
        self, dns_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        return self.request_action(
            "DetailDNSRule",
            json_body=True,
            ProductId=product_id or self.product_id,
            DNSId=dns_id,
            **kwargs,
        )

    def create_dns_rule(
        self,
        *,
        dc: str,
        ip_list: list[str],
        product_id: Optional[str] = None,
        dns_name: Optional[str] = None,
        type: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            Dc=dc,
            DNSName=dns_name,
            Type=type,
            IPList=ip_list,
            **kwargs,
        )
        return self._json_request("CreateDNSRule", body=body)

    def update_dns_rule(
        self,
        *,
        dns_id: str,
        product_id: Optional[str] = None,
        dns_name: Optional[str] = None,
        type: Optional[int] = None,
        ip_list: Optional[list[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            DNSId=dns_id,
            DNSName=dns_name,
            Type=type,
            IPList=ip_list,
            **kwargs,
        )
        return self._json_request("UpdateDNSRule", body=body)

    def delete_dns_rule(
        self, *, dns_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            DNSId=dns_id,
            **kwargs,
        )
        return self._json_request("DeleteDNSRule", body=body)

    def list_custom_routes(
        self,
        max_results: int = 10,
        next_token: Optional[str] = None,
        product_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return self.request_action(
            "ListCustomRoute",
            json_body=True,
            ProductId=product_id or self.product_id,
            MaxResults=max_results,
            NextToken=next_token,
            **kwargs,
        )

    def add_custom_route(
        self,
        *,
        zone: str,
        dst_ip: str,
        proxy_protocol: str,
        proxy_port: int,
        product_id: Optional[str] = None,
        custom_route_name: Optional[str] = None,
        proxy_user_name: Optional[str] = None,
        proxy_password: Optional[str] = None,
        proxy_cipher: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            CustomRouteName=custom_route_name,
            Zone=zone,
            DstIP=dst_ip,
            ProxyProtocol=proxy_protocol,
            ProxyPort=proxy_port,
            ProxyUserName=proxy_user_name,
            ProxyPassword=proxy_password,
            ProxyCipher=proxy_cipher,
            **kwargs,
        )
        return self._json_request("AddCustomRoute", body=body)

    def update_custom_route(
        self,
        *,
        custom_route_id: str,
        product_id: Optional[str] = None,
        custom_route_name: Optional[str] = None,
        dst_ip: Optional[str] = None,
        proxy_protocol: Optional[str] = None,
        proxy_port: Optional[int] = None,
        proxy_user_name: Optional[str] = None,
        proxy_password: Optional[str] = None,
        proxy_cipher: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            CustomRouteId=custom_route_id,
            CustomRouteName=custom_route_name,
            DstIP=dst_ip,
            ProxyProtocol=proxy_protocol,
            ProxyPort=proxy_port,
            ProxyUserName=proxy_user_name,
            ProxyPassword=proxy_password,
            ProxyCipher=proxy_cipher,
            **kwargs,
        )
        return self._json_request("UpdateCustomRoute", body=body)

    def delete_custom_route(
        self, *, custom_route_id: str, product_id: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        body = self.compact_body(
            ProductId=product_id or kwargs.pop("ProductId", self.product_id),
            CustomRouteId=custom_route_id,
            **kwargs,
        )
        return self._json_request("DeleteCustomRoute", body=body)

    # ========== 机房管理 ==========

    def list_dcs(
        self,
        product_id: Optional[str] = None,
        *,
        volc_region: Optional[str] = None,
        region: Optional[str] = None,
        isp: Optional[int] = None,
        server_type_code: Optional[str] = None,
        offset: Optional[int] = None,
        count: Optional[int] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        获取机房列表

        Args:
            product_id: 产品 ID（可选，默认使用初始化时的值）
            volc_region: 机房所在物理区域
            region: 机房所在大区 ID
            isp: 网络运营商 ID
            server_type_code: 云机规格
            offset: 分页偏移量
            count: 单次返回条数

        Returns:
            机房列表
        """
        body = self.compact_body(
            ProductId=product_id or self.product_id,
            VolcRegion=volc_region,
            Region=region,
            Isp=isp,
            ServerTypeCode=server_type_code,
            Offset=offset,
            Count=count,
            **kwargs,
        )
        return self._request("ListDc", body=body)
