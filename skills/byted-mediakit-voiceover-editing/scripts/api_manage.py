#!/usr/bin/env python3
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

import os
import json
import uuid
from pathlib import Path
from dotenv import load_dotenv
from vod_transport import get_vod_transport_client
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta
import hashlib
import secrets
from urllib.parse import quote, urlparse, urlencode, parse_qs, urlunparse
import urllib.request
import urllib.error
import time
from vod_local_upload import (
    STORAGE_STANDARD,
    TosMediaUploader,
    raise_for_vod_response,
    result_data,
    upload_tob_from_apply_data,
)

load_dotenv(
    dotenv_path=Path(__file__).resolve().parents[1] / ".env",
    override=False,
)


class ApiManage:
    """
    目标：将 `mcp_server_vod/src/vod/mcp_tools` 的工具实现，平移为本地可直接调用的方法。

    约束：
    - 不依赖 MCP 运行时（无 `create_mcp_server`、无 FastMCP/Context）。
    - VOD OpenAPI（action + version + params/body）经 `vod_transport.get_vod_transport_client()`：
      SkillHub 网关（ARK_SKILL_*）或直连火山签名（VOLC AK/SK）。
    """

    # OpenAPI Action -> Version 映射（来自仓库内 `mcp_server_vod/src/vod/api/config.py` 的 ApiInfo 定义）
    _VOD_VERSIONS: Dict[str, str] = {
        "ListSpace": "2021-01-01",
        "UploadMediaByUrl": "2020-08-01",
        "QueryUploadTaskInfo": "2020-08-01",
        "AsyncVCreativeTask": "2018-01-01",
        "GetVCreativeTaskResult": "2018-01-01",
        "GetVideoPlayInfo": "2018-01-01",
        "UpdateMediaPublishStatus": "2020-08-01",
        "StartExecution": "2025-01-01",
        "GetExecution": "2025-01-01",
        "ListDomain": "2023-01-01",
        "DescribeDomainConfig": "2023-07-01",
        "GetStorageConfig": "2023-07-01",
        "ApplyUploadInfo": "2022-01-01",
        "CommitUploadInfo": "2022-01-01",
    }

    def __init__(self):
        self.client = get_vod_transport_client()
        self._state: Dict[str, Any] = {}
        self._tos_uploader = TosMediaUploader()

    # ----------------------------
    # Low-level request helpers
    # ----------------------------
    def _get(
        self, action: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        # 统一做 JSON 解码，保证上层工具方法始终处理 dict
        try:
            response_text = self.client.get(
                action=action,
                version=self._VOD_VERSIONS[action],
                params=params or None,
            )
            return (
                json.loads(response_text)
                if isinstance(response_text, str)
                else (response_text or {})
            )
        except Exception as e:
            raise Exception(
                f"VOD GET failed: action={action}, params={params}, error={e}"
            )

    def _post(self, action: str, body: Dict[str, Any]) -> Dict[str, Any]:
        # 统一做 JSON 解码，保证上层工具方法始终处理 dict
        try:
            response_text = self.client.post(
                action=action,
                version=self._VOD_VERSIONS[action],
                body=body,
            )
            return (
                json.loads(response_text)
                if isinstance(response_text, str)
                else (response_text or {})
            )
        except Exception as e:
            raise Exception(f"VOD POST failed: action={action}, body={body}, error={e}")

    def list_space(self) -> bool:
        """
        检查环境变量中指定的 spaceName 是否存在

        Returns:
            True 表示空间存在，False 表示不存在
        """
        space_name = os.getenv("VOLC_SPACE_NAME")
        if not space_name:
            raise ValueError("Missing VOLC_SPACE_NAME environment variable")

        try:
            response = self._get("ListSpace")
            spaces = response.get("Result", [])

            for space in spaces:
                if space.get("SpaceName") == space_name:
                    return True

            return False
        except Exception as e:
            raise Exception(f"Failed to check space existence: {str(e)}")

    # ----------------------------
    # video_play helpers (ported from mcp_tools/video_play.py)
    # ----------------------------
    # 说明：播放直链的生成依赖「域名配置 +（可选）鉴权规则」或「存储配置兜底」。
    @staticmethod
    def _random_string(length: int) -> str:
        alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def _encode_path_str(s: str = "") -> str:
        return quote(s, safe="-_.~$&+,/:;=@")

    @staticmethod
    def _encode_rfc3986_uri_component(s: str) -> str:
        return quote(s, safe=":/?&=%-_.~")

    @staticmethod
    def _parse_time(value: Any) -> Optional[datetime]:
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(float(value), tz=timezone.utc)
            except Exception:
                return None
        if isinstance(value, str):
            try:
                v = value.replace("Z", "+00:00") if "Z" in value else value
                return datetime.fromisoformat(v)
            except Exception:
                return None
        return None

    @classmethod
    def _is_https_available(cls, certificate: Dict[str, Any]) -> bool:
        if certificate and certificate.get("HttpsStatus") == "enable":
            exp = cls._parse_time(certificate.get("ExpiredAt"))
            if exp:
                return exp > datetime.now(timezone.utc)
        return False

    @staticmethod
    def _str_to_number(s: Any, default: Any = None) -> Any:
        if not isinstance(s, str):
            return default
        s_clean = s.strip().replace(",", "")
        try:
            if s_clean.isdigit() or (
                s_clean.startswith(("+", "-")) and s_clean[1:].isdigit()
            ):
                return int(s_clean)
            return float(s_clean)
        except Exception:
            return default

    def _get_domain_config(
        self, domain: str, space_name: str, domain_type: str = "play"
    ) -> Dict[str, Any]:
        detail = self._get(
            "DescribeDomainConfig",
            params={
                "SpaceName": space_name,
                "Domain": domain,
                "DomainType": domain_type,
            },
        )
        result = detail.get("Result", {}) if isinstance(detail, dict) else {}
        cdn_config = result.get("Config") or {}
        signed_url_auth_control = cdn_config.get("SignedUrlAuthControl") or {}
        signed_url_auth_rules = (
            signed_url_auth_control.get("SignedUrlAuth") or {}
        ).get("SignedUrlAuthRules", [])
        if not signed_url_auth_rules:
            return {}
        signed_url_auth_action = (signed_url_auth_rules[0] or {}).get(
            "SignedUrlAuthAction", {}
        ) or {}
        base_domain = result.get("Domain", {}) or {}
        status = (
            "enable"
            if base_domain.get("ConfigStatus") == "online"
            else base_domain.get("ConfigStatus")
        )
        return {
            "AuthType": signed_url_auth_action.get("URLAuthType"),
            "AuthKey": signed_url_auth_action.get("MasterSecretKey")
            or signed_url_auth_action.get("BackupSecretKey")
            or "",
            "Status": status,
            "Domain": base_domain.get("Domain", ""),
        }

    def _get_available_domain(self, space_name: str) -> List[Dict[str, Any]]:
        cached = ((self._state.get("available_domains") or {}).get(space_name)) or []
        if cached:
            return cached

        offset = 0
        total = 1
        domain_list: List[Dict[str, Any]] = []
        while offset < total:
            data = self._get(
                "ListDomain",
                params={
                    "SpaceName": space_name,
                    "SourceStationType": 1,
                    "DomainType": "play",
                    "Offset": offset,
                },
            )
            offset = int(data.get("Offset", 0) or 0)
            total = int(data.get("Total", 0) or 0)
            result = data.get("Result", {}) or {}
            instances = (result.get("PlayInstanceInfo") or {}).get(
                "ByteInstances"
            ) or []
            for item in instances:
                domains = item.get("Domains") or []
                for domain in domains:
                    d = dict(domain)
                    d["SourceStationType"] = 1
                    d["DomainType"] = "play"
                    domain_list.append(d)

        domain_list = [d for d in domain_list if d.get("CdnStatus") == "enable"]
        enriched: List[Dict[str, Any]] = []
        for d in domain_list:
            auth_info = self._get_domain_config(
                d.get("Domain", ""), space_name, d.get("DomainType", "play")
            )
            d2 = dict(d)
            d2["AuthInfo"] = auth_info
            enriched.append(d2)

        available = [
            d
            for d in enriched
            if (not d.get("AuthInfo"))
            or ((d.get("AuthInfo") or {}).get("AuthType") == "typea")
        ]

        self._state["available_domains"] = {
            **(self._state.get("available_domains") or {}),
            space_name: available,
        }
        return available

    def _gen_url(
        self,
        space_name: str,
        domain_obj: Dict[str, Any],
        path: str,
        expired_minutes: int,
    ) -> str:
        available_domains_list = self._get_available_domain(space_name)
        if available_domains_list:
            domain_obj = available_domains_list[0]
        is_https = self._is_https_available(domain_obj.get("Certificate") or {})
        file_name = f"/{path}"
        auth_info = domain_obj.get("AuthInfo") or {}
        if auth_info.get("AuthType") == "typea":
            expire_ts = int(
                (
                    datetime.now(timezone.utc) + timedelta(minutes=expired_minutes)
                ).timestamp()
            )
            rand_str = self._random_string(16)
            key = auth_info.get("AuthKey") or ""
            md5_input = f"{self._encode_path_str(file_name)}-{expire_ts}-{rand_str}-0-{key}".encode(
                "utf-8"
            )
            md5_str = hashlib.md5(md5_input).hexdigest()
            url = f"{'https' if is_https else 'http'}://{domain_obj.get('Domain')}{file_name}?auth_key={expire_ts}-{rand_str}-0-{md5_str}"
            return self._encode_rfc3986_uri_component(url)
        url = (
            f"{'https' if is_https else 'http'}://{domain_obj.get('Domain')}{file_name}"
        )
        return self._encode_rfc3986_uri_component(url)

    def _gen_wild_url(self, storage_config: Dict[str, Any], file_name: str) -> str:
        file_path = f"/{file_name}"
        conf = storage_config.get("StorageUrlAuthConfig") or {}
        if (
            storage_config.get("StorageType") == "volc"
            and conf.get("Type") == "cdn_typea"
            and conf.get("Status") == "enable"
        ):
            type_a = conf.get("TypeAConfig") or {}
            expire_seconds = self._str_to_number(type_a.get("ExpireTime") or 0, 0) or 0
            expire_ts = int(
                (
                    datetime.now(timezone.utc) + timedelta(seconds=expire_seconds)
                ).timestamp()
            )
            rand_str = self._random_string(16)
            key = type_a.get("MasterKey") or type_a.get("BackupKey") or ""
            md5_input = f"{self._encode_path_str(file_path)}-{expire_ts}-{rand_str}-0-{key}".encode(
                "utf-8"
            )
            md5_str = hashlib.md5(md5_input).hexdigest()
            sig_arg = type_a.get("SignatureArgs") or "auth_key"
            signed = f"{storage_config.get('StorageHost')}{file_path}?{sig_arg}={expire_ts}-{rand_str}-0-{md5_str}&preview=1"
            return self._encode_rfc3986_uri_component(signed)
        if (
            storage_config.get("StorageType") == "volc"
            and conf.get("Status") == "disable"
        ):
            signed = f"{storage_config.get('StorageHost')}{file_path}?preview=1"
            return self._encode_rfc3986_uri_component(signed)
        return ""

    def get_storage_config(self, space_name: str) -> Dict[str, Any]:
        cached = ((self._state.get("storage_config") or {}).get(space_name)) or {}
        if cached:
            return cached
        reqs = self._get("GetStorageConfig", params={"SpaceName": space_name})
        storage_config = reqs.get("Result") or {}
        self._state["storage_config"] = {
            **(self._state.get("storage_config") or {}),
            space_name: storage_config,
        }
        return storage_config

    def get_play_url(
        self,
        type: str,
        source: str,
        space_name: Optional[str] = None,
        expired_minutes: int = 60,
    ) -> str:
        """
        directurl: 生成可播放直链（可能带 typea 鉴权参数）
        vid: 通过 GetVideoPlayInfo 获取 PlayURL
        """
        if not space_name:
            space_name = os.getenv("VOLC_SPACE_NAME")
        if not space_name or not isinstance(space_name, str) or not space_name.strip():
            raise ValueError("get_play_url: space_name is required")
        if not source or not isinstance(source, str) or not source.strip():
            raise ValueError("get_play_url: source is required")

        if type == "directurl":
            available_domains_list = self._get_available_domain(space_name)
            if available_domains_list:
                return self._gen_url(
                    space_name, available_domains_list[0], source, expired_minutes
                )
            storage_config = self.get_storage_config(space_name)
            return self._gen_wild_url(storage_config, source)
        if type == "vid":
            info = self.get_play_video_info(source, space_name)
            return info.get("PlayURL", "")
        raise ValueError(f"get_play_url: unsupported type: {type}")

    def get_video_audio_info(
        self, type: str, source: str, space_name: Optional[str] = None
    ) -> Dict[str, Any]:
        if not space_name:
            space_name = os.getenv("VOLC_SPACE_NAME")
        if not space_name or not isinstance(space_name, str) or not space_name.strip():
            raise ValueError("get_video_audio_info: space_name is required")
        if not source or not isinstance(source, str) or not source.strip():
            raise ValueError("get_video_audio_info: source is required")

        if type == "directurl":
            play_url = self.get_play_url("directurl", source, space_name, 60)
            if not play_url:
                raise Exception("get_video_audio_info: failed to get play url")
            parsed = urlparse(play_url)
            query_params = parse_qs(parsed.query)
            query_params["x-vod-process"] = ["video/info"]
            new_query = urlencode(query_params, doseq=True)
            info_url = urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    new_query,
                    parsed.fragment,
                )
            )
            try:
                req = urllib.request.Request(info_url)
                with urllib.request.urlopen(req, timeout=30) as response:
                    result_data = json.loads(response.read().decode("utf-8"))
            except urllib.error.URLError as e:
                raise Exception(
                    f"get_video_audio_info: failed to fetch video info: {e}"
                )
            except json.JSONDecodeError as e:
                raise Exception(
                    f"get_video_audio_info: failed to parse JSON response: {e}"
                )

            format_info = result_data.get("format", {}) or {}
            streams = result_data.get("streams", []) or []
            video_stream = None
            audio_stream = None
            for stream in streams:
                codec_type = stream.get("codec_type", "")
                if codec_type == "video" and video_stream is None:
                    video_stream = stream
                elif codec_type == "audio" and audio_stream is None:
                    audio_stream = stream

            duration_value = format_info.get("duration")
            duration = float(duration_value) if duration_value is not None else 0
            size_value = format_info.get("size")
            size = float(size_value) if size_value is not None else 0

            result: Dict[str, Any] = {
                "FormatName": format_info.get("format_name", ""),
                "Duration": duration,
                "Size": size,
                "BitRate": format_info.get("bit_rate", ""),
                "CodecName": "",
                "AvgFrameRate": "",
                "Width": 0,
                "Height": 0,
                "Channels": 0,
                "SampleRate": "",
                "BitsPerSample": "",
                "PlayURL": play_url,
            }

            if video_stream:
                result["CodecName"] = video_stream.get("codec_name", "")
                result["AvgFrameRate"] = video_stream.get("avg_frame_rate", "")
                result["Width"] = (
                    int(video_stream.get("width", 0))
                    if video_stream.get("width")
                    else 0
                )
                result["Height"] = (
                    int(video_stream.get("height", 0))
                    if video_stream.get("height")
                    else 0
                )
                if not result["BitRate"]:
                    result["BitRate"] = str(video_stream.get("bit_rate", ""))

            if audio_stream:
                result["Channels"] = (
                    int(audio_stream.get("channels", 0))
                    if audio_stream.get("channels")
                    else 0
                )
                result["SampleRate"] = str(audio_stream.get("sample_rate", ""))
                bits_per_sample = audio_stream.get("bits_per_sample")
                if bits_per_sample not in (None, 0):
                    result["BitsPerSample"] = str(bits_per_sample)
            return result

        if type == "vid":
            info = self.get_play_video_info(source, space_name)
            return {
                "FormatName": info.get("FormatName", ""),
                "Duration": float(info.get("Duration") or 0),
                "Size": float(info.get("Size") or 0),
                "BitRate": info.get("BitRate", ""),
                "CodecName": info.get("CodecName", ""),
                "AvgFrameRate": info.get("AvgFrameRate", ""),
                "Width": int(info.get("Width") or 0),
                "Height": int(info.get("Height") or 0),
                "Channels": 0,
                "SampleRate": "",
                "BitsPerSample": "",
                "PlayURL": info.get("PlayURL", ""),
            }

        raise ValueError(f"get_video_audio_info: unsupported type: {type}")

    def update_media_publish_status(
        self, vid: str, space_name: str, publish_status: str
    ) -> str:
        try:
            self._post(
                "UpdateMediaPublishStatus", {"Vid": vid, "Status": publish_status}
            )
            return "success"
        except Exception as e:
            raise Exception(f"update_media_publish_status failed: {e}")

    def get_play_video_info(
        self,
        vid: str,
        space_name: str,
        output_type: str = "CDN",
        *,
        _publish_attempted: bool = False,
    ) -> Dict[str, Any]:
        reqs = self._get(
            "GetVideoPlayInfo",
            params={
                "Space": space_name,
                "Vid": vid,
                "DataType": 0,
                "OutputType": output_type,
            },
        )
        result = reqs.get("Result", {}) or {}
        video_detail = result.get("VideoDetail", {}) or {}
        info = (video_detail.get("VideoDetailInfo") or {}) or {}
        play_info = info.get("PlayInfo", {}) or {}
        duration_value = info.get("Duration")
        duration = float(duration_value) if duration_value is not None else 0
        format_name = info.get("Format", "")
        size_value = info.get("Size")
        size = float(size_value) if size_value is not None else 0
        bit_rate = str(info.get("Bitrate", "")) if info.get("Bitrate") else ""
        codec_name = info.get("Codec", "")
        avg_frame_rate = str(info.get("Fps", "")) if info.get("Fps") else ""
        width = int(info.get("Width", 0)) if info.get("Width") else 0
        height = int(info.get("Height", 0)) if info.get("Height") else 0

        url = None
        if info.get("PublishStatus") == "Published":
            url = play_info.get("MainPlayURL") or play_info.get("BackupPlayUrl")
            if output_type == "CDN" and (not url):
                url = self.get_play_video_info(
                    vid, space_name, "Origin", _publish_attempted=_publish_attempted
                ).get("PlayURL", "")
        else:
            # 仅尝试一次发布更新，避免「已调 Update 但 Get 仍非 Published」时无限递归
            if _publish_attempted:
                url = play_info.get("MainPlayURL") or play_info.get("BackupPlayUrl")
                if not url:
                    raise Exception(
                        f"{vid}: GetVideoPlayInfo PublishStatus is not Published after "
                        "UpdateMediaPublishStatus; no PlayURL in response"
                    )
            elif (
                self.update_media_publish_status(vid, space_name, "Published")
                == "success"
            ):
                time.sleep(0.35)
                url = self.get_play_video_info(
                    vid, space_name, "Origin", _publish_attempted=True
                ).get("PlayURL", "")
            else:
                raise Exception("update publish status failed")

        if not url:
            raise Exception(f"{vid}: get publish url failed")

        return {
            "PlayURL": url,
            "Duration": duration,
            "FormatName": format_name,
            "Size": size,
            "BitRate": bit_rate,
            "CodecName": codec_name,
            "AvgFrameRate": avg_frame_rate,
            "Width": width,
            "Height": height,
        }

    # ----------------------------
    # edit (VCreative) tools (ported from mcp_tools/edit.py)
    # ----------------------------
    @staticmethod
    def _format_source(type: str, source: str) -> str:
        if not source:
            return source
        if source.startswith(("vid://", "directurl://", "http://", "https://")):
            return source
        if type == "vid":
            return f"vid://{source}"
        if type == "directurl":
            return f"directurl://{source}"
        return source

    def _async_vcreative_task(
        self, uploader_space: str, workflow_id: str, param_obj: Dict[str, Any]
    ) -> Dict[str, Any]:
        payload = {
            "ParamObj": param_obj,
            "Uploader": uploader_space,
            "WorkflowId": workflow_id,
        }
        resp = self._post("AsyncVCreativeTask", payload)
        result = resp.get("Result", {}) if isinstance(resp, dict) else {}
        base_resp = result.get("BaseResp", {}) or {}
        return {
            "VCreativeId": result.get("VCreativeId", ""),
            "Code": result.get("Code"),
            "StatusMessage": base_resp.get("StatusMessage", ""),
            "StatusCode": base_resp.get("StatusCode", 0),
        }

    def get_v_creative_task_result_once(
        self, VCreativeId: str, space_name: Optional[str] = None
    ) -> Dict[str, Any]:
        if (
            not VCreativeId
            or not isinstance(VCreativeId, str)
            or not VCreativeId.strip()
        ):
            raise ValueError("get_v_creative_task_result: VCreativeId is required")
        if not space_name:
            space_name = os.getenv("VOLC_SPACE_NAME")
        if not space_name or not isinstance(space_name, str) or not space_name.strip():
            raise ValueError("get_v_creative_task_result: space_name is required")

        reqs = self._get(
            "GetVCreativeTaskResult",
            params={"VCreativeId": VCreativeId, "SpaceName": space_name},
        )
        result = reqs.get("Result", {}) if isinstance(reqs, dict) else {}
        status = result.get("Status", "")
        if status != "success":
            return result

        output_json = result.get("OutputJson", {})
        temp_output: Dict[str, Any] = {}
        if isinstance(output_json, str):
            try:
                temp_output = json.loads(output_json)
            except json.JSONDecodeError:
                temp_output = {}
        elif isinstance(output_json, dict):
            temp_output = output_json

        vid = temp_output.get("vid")
        if vid is None:
            raise Exception("get_v_creative_task_result: vid is None")

        play_info = self.get_play_video_info(str(vid), space_name)
        return {
            "OutputJson": {
                "vid": vid,
                "resolution": temp_output.get("resolution"),
                "duration": temp_output.get("duration"),
                "filename": temp_output.get("filename"),
                "url": play_info.get("PlayURL", ""),
            },
            "Status": status,
        }

    def get_v_creative_task_result(
        self,
        VCreativeId: str,
        space_name: Optional[str] = None,
        interval: float = 2.0,
        max_retries: int = 10,
    ) -> Dict[str, Any]:
        # 同步轮询版本（原 MCP 实现会通过 ctx.report_progress 异步上报，这里移除）。
        last: Optional[Dict[str, Any]] = None
        for _ in range(max_retries):
            last = self.get_v_creative_task_result_once(VCreativeId, space_name)
            status = last.get("Status") if isinstance(last, dict) else None
            if status in ("success", "failed_run"):
                return last
            if status == "running":
                return last
            time.sleep(interval)
        return last or {}

    def audio_video_stitching(
        self,
        type: str,
        space_name: str,
        videos: Optional[List[str]] = None,
        audios: Optional[List[str]] = None,
        transitions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if not space_name or not isinstance(space_name, str) or not space_name.strip():
            raise ValueError("audio_video_stitching: space_name is required")
        param_type = type or "video"
        if param_type == "audio":
            if not audios or not isinstance(audios, list):
                raise ValueError(
                    "audio_video_stitching: audios is required for audio type"
                )
            formatted_audios: List[Any] = []
            for a in audios:
                if isinstance(a, str):
                    if a.startswith(("vid://", "directurl://", "http://", "https://")):
                        formatted_audios.append(a)
                    else:
                        formatted_audios.append(self._format_source("vid", a))
                else:
                    formatted_audios.append(a)
            param_obj = {"space_name": space_name, "audios": formatted_audios}
            workflow_id = "loki://158487089"
        else:
            if not videos or not isinstance(videos, list):
                raise ValueError(
                    "audio_video_stitching: videos is required for video type"
                )
            formatted_videos: List[Any] = []
            for v in videos:
                if isinstance(v, str):
                    if v.startswith(("vid://", "directurl://", "http://", "https://")):
                        formatted_videos.append(v)
                    else:
                        formatted_videos.append(self._format_source("vid", v))
                else:
                    formatted_videos.append(v)
            param_obj = {
                "space_name": space_name,
                "videos": formatted_videos,
                "transitions": transitions or [],
            }
            workflow_id = "loki://154775772"
        return self._async_vcreative_task(space_name, workflow_id, param_obj)

    def audio_video_clipping(
        self,
        type: str,
        source: str,
        start_time: float,
        end_time: float,
        space_name: str,
    ) -> Dict[str, Any]:
        if not space_name or not isinstance(space_name, str) or not space_name.strip():
            raise ValueError("audio_video_clipping: space_name is required")
        if source is None or (isinstance(source, str) and not source.strip()):
            raise ValueError("audio_video_clipping: source is required")
        if end_time <= start_time:
            raise ValueError("audio_video_clipping: end_time must be > start_time")
        param_type = type or "video"
        formatted_source = self._format_source(
            param_type if param_type in ("vid", "directurl") else "vid", source
        )
        param_obj = {
            "space_name": space_name,
            "source": formatted_source,
            "end_time": end_time,
            "start_time": start_time,
        }
        workflow_id = (
            "loki://158666752" if param_type == "audio" else "loki://154419276"
        )
        return self._async_vcreative_task(space_name, workflow_id, param_obj)

    def flip_video(
        self,
        type: str,
        source: str,
        space_name: str,
        flip_x: bool = False,
        flip_y: bool = False,
    ) -> Dict[str, Any]:
        if not space_name or not isinstance(space_name, str) or not space_name.strip():
            raise ValueError("flip_video: space_name is required")
        formatted_source = self._format_source(type or "vid", source)
        param_obj = {
            "space_name": space_name,
            "source": formatted_source,
            "flip_x": bool(flip_x),
            "flip_y": bool(flip_y),
        }
        return self._async_vcreative_task(space_name, "loki://165221855", param_obj)

    def speedup_video(
        self, type: str, source: str, space_name: str, speed: float = 1.0
    ) -> Dict[str, Any]:
        if not (0.1 <= float(speed) <= 4):
            raise ValueError("speedup_video: speed must be between 0.1 and 4")
        formatted_source = self._format_source(type or "vid", source)
        param_obj = {
            "space_name": space_name,
            "source": formatted_source,
            "speed": float(speed),
        }
        return self._async_vcreative_task(space_name, "loki://165223469", param_obj)

    def speedup_audio(
        self, type: str, source: str, space_name: str, speed: float = 1.0
    ) -> Dict[str, Any]:
        if not (0.1 <= float(speed) <= 4):
            raise ValueError("speedup_audio: speed must be between 0.1 and 4")
        formatted_source = self._format_source(type or "vid", source)
        param_obj = {
            "space_name": space_name,
            "source": formatted_source,
            "speed": float(speed),
        }
        return self._async_vcreative_task(space_name, "loki://174663067", param_obj)

    def image_to_video(
        self,
        images: List[Dict[str, Any]],
        space_name: str,
        transitions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if not images or not isinstance(images, list):
            raise ValueError("image_to_video: images must be a non-empty list")
        formatted_images: List[Dict[str, Any]] = []
        for image in images:
            if not isinstance(image, dict):
                formatted_images.append(image)  # type: ignore[list-item]
                continue
            img_type = image.get("type", "vid")
            img_source = image.get("source", "")
            formatted_source = (
                self._format_source(img_type, img_source)
                if img_type in ("vid", "directurl")
                else img_source
            )
            formatted = {"type": img_type, "source": formatted_source}
            for k in ("duration", "animation_type", "animation_in", "animation_out"):
                if k in image:
                    formatted[k] = image[k]
            formatted_images.append(formatted)
        param_obj = {
            "space_name": space_name,
            "images": formatted_images,
            "transitions": transitions or [],
        }
        return self._async_vcreative_task(space_name, "loki://167979998", param_obj)

    def compile_video_audio(
        self,
        video: Dict[str, Any],
        audio: Dict[str, Any],
        space_name: str,
        is_audio_reserve: bool = True,
        is_video_audio_sync: bool = False,
        sync_mode: str = "video",
        sync_method: str = "trim",
    ) -> Dict[str, Any]:
        if not isinstance(video, dict) or not isinstance(audio, dict):
            raise ValueError("compile_video_audio: video and audio must be dicts")
        v_type = video.get("type", "vid")
        v_source = video.get("source", "")
        a_type = audio.get("type", "vid")
        a_source = audio.get("source", "")
        formatted_v = (
            self._format_source(v_type, v_source)
            if v_type in ("vid", "directurl")
            else v_source
        )
        formatted_a = (
            self._format_source(a_type, a_source)
            if a_type in ("vid", "directurl")
            else a_source
        )
        param_obj: Dict[str, Any] = {
            "space_name": space_name,
            "video": formatted_v,
            "audio": formatted_a,
            "is_audio_reserve": bool(is_audio_reserve),
            "is_video_audio_sync": bool(is_video_audio_sync),
        }
        if is_video_audio_sync:
            param_obj["sync_mode"] = sync_mode
            param_obj["sync_method"] = sync_method
        return self._async_vcreative_task(space_name, "loki://167984726", param_obj)

    def extract_audio(
        self, type: str, source: str, space_name: str, format: str = "mp3"
    ) -> Dict[str, Any]:
        if format not in ("mp3", "m4a"):
            raise ValueError("extract_audio: format must be mp3 or m4a")
        formatted_source = self._format_source(type or "vid", source)
        param_obj = {
            "space_name": space_name,
            "source": formatted_source,
            "format": format,
        }
        return self._async_vcreative_task(space_name, "loki://167986559", param_obj)

    def mix_audios(
        self, audios: List[Dict[str, Any]], space_name: str
    ) -> Dict[str, Any]:
        if not audios or not isinstance(audios, list):
            raise ValueError("mix_audios: audios must be a non-empty list")
        formatted: List[Any] = []
        for a in audios:
            if isinstance(a, dict):
                a_type = a.get("type", "vid")
                a_source = a.get("source", "")
                formatted_source = (
                    self._format_source(a_type, a_source)
                    if a_type in ("vid", "directurl")
                    else a_source
                )
                formatted.append(formatted_source)
            else:
                formatted.append(a)
        param_obj = {"space_name": space_name, "audios": formatted}
        return self._async_vcreative_task(space_name, "loki://167987532", param_obj)

    def add_sub_video(
        self,
        video: Dict[str, Any],
        sub_video: Dict[str, Any],
        space_name: str,
        sub_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        v_type = video.get("type", "vid")
        v_source = video.get("source", "")
        s_type = sub_video.get("type", "vid")
        s_source = sub_video.get("source", "")
        formatted_v = (
            self._format_source(v_type, v_source)
            if v_type in ("vid", "directurl")
            else v_source
        )
        formatted_s = (
            self._format_source(s_type, s_source)
            if s_type in ("vid", "directurl")
            else s_source
        )
        param_obj: Dict[str, Any] = {
            "space_name": space_name,
            "video": formatted_v,
            "sub_video": formatted_s,
        }
        if sub_options and isinstance(sub_options, dict):
            param_obj["sub_options"] = {**sub_options}
        return self._async_vcreative_task(space_name, "loki://168021310", param_obj)

    def add_subtitle(
        self,
        video: Dict[str, Any],
        space_name: str,
        subtitle_url: Optional[str] = None,
        text_list: Optional[List[Dict[str, Any]]] = None,
        subtitle_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not subtitle_url and not text_list:
            raise ValueError("add_subtitle: subtitle_url or text_list is required")
        v_type = video.get("type", "vid")
        v_source = video.get("source", "")
        formatted_v = (
            self._format_source(v_type, v_source)
            if v_type in ("vid", "directurl")
            else v_source
        )
        param_obj: Dict[str, Any] = {"space_name": space_name, "video": formatted_v}
        if subtitle_url:
            param_obj["subtitle_url"] = subtitle_url
        else:
            param_obj["text_list"] = text_list or []
        if subtitle_config:
            param_obj["subtitle_config"] = subtitle_config
        return self._async_vcreative_task(space_name, "loki://168214785", param_obj)

    # ----------------------------
    # StartExecution/GetExecution tools (ported from mcp_tools/* + utils/transcode.py)
    # ----------------------------
    # 说明：这类工具走「媒体处理执行引擎」，启动用 StartExecution，查询用 GetExecution，

    def _build_media_input(
        self, asset_type: str, asset_value: str, space_name: str
    ) -> Dict[str, Any]:
        if asset_type not in {"Vid", "DirectUrl"}:
            raise ValueError(f"type must be Vid or DirectUrl, but got {asset_type}")
        if not asset_value:
            raise ValueError("media asset id is required")
        if not space_name:
            raise ValueError("spaceName is required")
        media_input: Dict[str, Any] = {"Type": asset_type}
        if asset_type == "Vid":
            media_input["Vid"] = asset_value
        else:
            media_input["DirectUrl"] = {
                "FileName": asset_value,
                "SpaceName": space_name,
            }
        return media_input

    def _start_execution(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = self._post("StartExecution", payload)
        result = resp.get("Result", {}) if isinstance(resp, dict) else {}
        return {"RunId": (result.get("RunId") or "")}

    def get_media_execution_task_result(self, type: str, run_id: str) -> Dict[str, Any]:
        valid_types = {
            "portraitImageRetouching",
            "greenScreen",
            "intelligentSlicing",
            "voiceSeparation",
            "subtitlesRemoval",
            "ocr",
            "asr",
            "audioNoiseReduction",
            "videoInterlacing",
            "videSuperResolution",
            "enhanceVideo",
        }
        if type not in valid_types:
            raise ValueError(
                f"type must be one of {sorted(valid_types)}, but got {type}"
            )
        if not run_id or not run_id.strip():
            raise ValueError("runId must be provided")

        response = self._get("GetExecution", params={"RunId": run_id})
        video_urls: List[Dict[str, Any]] = []
        audio_urls: List[Dict[str, Any]] = []
        texts: List[Dict[str, Any]] = []

        temp_result = response.get("Result", {}) if isinstance(response, dict) else {}
        space_name = (temp_result.get("Meta", {}) or {}).get("SpaceName", "")
        output = (temp_result.get("Output", {}) or {}).get("Task", {}) or {}
        status = temp_result.get("Status", "")
        if status != "Success":
            return {
                "Status": status,
                "Code": temp_result.get("Code", ""),
                "SpaceName": space_name,
            }

        def handle_transcode_data(
            data: Dict[str, Any], space_name_inner: str
        ) -> Dict[str, Any]:
            file_id = data.get("FileId")
            store_uri = data.get("StoreUri")
            file_name = ""
            if store_uri and isinstance(store_uri, str):
                parsed = urlparse(store_uri)
                parts = parsed.path.split("/")[1:]
                file_name = "/".join(parts)
            return {
                "FileId": file_id,
                "DirectUrl": file_name,
                "Url": self.get_play_url("directurl", file_name, space_name_inner),
            }

        enhance_type = {
            "enhanceVideo",
            "videSuperResolution",
            "videoInterlacing",
            "audioNoiseReduction",
        }
        video_matting = {"greenScreen", "portraitImageRetouching"}

        if type in enhance_type:
            enhance_info = handle_transcode_data(
                output.get("Enhance", {}) or {}, space_name
            )
            video_urls.append(enhance_info)
        elif type in video_matting:
            video_matting_result = output.get("VideoMatting", {}) or {}
            video_file = video_matting_result.get("Video", {}) or {}
            file_name = video_file.get("FileName", "")
            video_urls.append(
                {
                    "DirectUrl": file_name,
                    "Vid": video_file.get("Vid", ""),
                    "Url": self.get_play_url("directurl", file_name, space_name),
                }
            )
        elif type == "intelligentSlicing":
            segment = output.get("Segment", {}) or {}
            segments = segment.get("Segments", []) or []
            for seg in segments:
                seg_file = seg.get("File", {}) or {}
                seg_file_name = seg_file.get("FileName", "")
                video_urls.append(
                    {
                        "DirectUrl": seg_file_name,
                        "Vid": seg_file.get("Vid", ""),
                        "Url": self.get_play_url(
                            "directurl", seg_file_name, space_name
                        ),
                    }
                )
        elif type == "voiceSeparation":
            audio_extract = output.get("AudioExtract", {}) or {}
            voice_files = audio_extract.get("Voice", {}) or {}
            background_files = audio_extract.get("Background", {}) or {}
            voice_name = voice_files.get("FileName", "")
            bg_name = background_files.get("FileName", "")
            audio_urls.append(
                {
                    "DirectUrl": voice_name,
                    "Vid": voice_files.get("Vid", ""),
                    "Type": "voice",
                    "Url": self.get_play_url("directurl", voice_name, space_name),
                }
            )
            audio_urls.append(
                {
                    "DirectUrl": bg_name,
                    "Vid": background_files.get("Vid", ""),
                    "Type": "background",
                    "Url": self.get_play_url("directurl", bg_name, space_name),
                }
            )
        elif type == "subtitlesRemoval":
            erase = output.get("Erase", {}) or {}
            erase_file = erase.get("File", {}) or {}
            file_name = erase_file.get("FileName", "")
            video_urls.append(
                {
                    "DirectUrl": file_name,
                    "Vid": erase_file.get("Vid", ""),
                    "Url": self.get_play_url("directurl", file_name, space_name),
                }
            )
        elif type == "ocr":
            ocr = output.get("Ocr", {}) or {}
            texts = ocr.get("Texts", []) or []
        elif type == "asr":
            asr = output.get("Asr", {}) or {}
            utterances = asr.get("Utterances", []) or []
            for u in utterances:
                attr = u.get("Attribute", {}) or {}
                texts.append(
                    {
                        "Speaker": attr.get("Speaker", ""),
                        "Text": u.get("Text", ""),
                        "StartTime": u.get("Start"),
                        "EndTime": u.get("End"),
                    }
                )

        return {
            "Code": temp_result.get("Code", ""),
            "SpaceName": space_name,
            "VideoUrls": video_urls,
            "AudioUrls": audio_urls,
            "Texts": texts,
            "Status": status,
        }

    # --- intelligent_slicing ---
    def intelligent_slicing_task(
        self, type: str, video: str, space_name: str
    ) -> Dict[str, Any]:
        media_input = self._build_media_input(type, video, space_name)
        params = {
            "Input": media_input,
            "Operation": {
                "Type": "Task",
                "Task": {
                    "Type": "Segment",
                    "Segment": {"MinDuration": 2.0, "Threshold": 15.0},
                },
            },
        }
        return self._start_execution(params)

    # --- intelligent_matting ---
    def green_screen_task(
        self, type: str, video: str, space_name: str, output_format: str = "WEBM"
    ) -> Dict[str, Any]:
        valid_formats = {"MOV", "WEBM"}
        fmt = (output_format or "").upper()
        if fmt not in valid_formats:
            raise ValueError(
                f"output_format must be one of {sorted(valid_formats)}, but got {output_format}"
            )
        media_input = self._build_media_input(type, video, space_name)
        params = {
            "Input": media_input,
            "Operation": {
                "Type": "Task",
                "Task": {
                    "Type": "VideoMatting",
                    "VideoMatting": {
                        "Model": "GreenScreen",
                        "VideoOption": {"Format": fmt},
                        "NewVid": True,
                    },
                },
            },
        }
        return self._start_execution(params)

    def portrait_image_retouching_task(
        self, type: str, video: str, space_name: str, output_format: str = "WEBM"
    ) -> Dict[str, Any]:
        valid_formats = {"MOV", "WEBM"}
        fmt = (output_format or "").upper()
        if fmt not in valid_formats:
            raise ValueError(
                f"output_format must be one of {sorted(valid_formats)}, but got {output_format}"
            )
        media_input = self._build_media_input(type, video, space_name)
        params = {
            "Input": media_input,
            "Operation": {
                "Type": "Task",
                "Task": {
                    "Type": "VideoMatting",
                    "VideoMatting": {
                        "Model": "Human",
                        "VideoOption": {"Format": fmt},
                        "NewVid": True,
                    },
                },
            },
        }
        return self._start_execution(params)

    # --- audio_processing ---
    def audio_noise_reduction_task(
        self, type: str, audio: str, space_name: str
    ) -> Dict[str, Any]:
        media_input = self._build_media_input(type, audio, space_name)
        params = {
            "Input": media_input,
            "Operation": {
                "Type": "Task",
                "Task": {
                    "Type": "Enhance",
                    "Enhance": {
                        "Type": "Custom",
                        "Modules": [{"Type": "AudioDenoise"}],
                    },
                },
            },
        }
        return self._start_execution(params)

    def voice_separation_task(
        self, type: str, video: str, space_name: str
    ) -> Dict[str, Any]:
        media_input = self._build_media_input(type, video, space_name)
        params = {
            "Input": media_input,
            "Operation": {
                "Type": "Task",
                "Task": {"Type": "AudioExtract", "AudioExtract": {"Voice": True}},
            },
        }
        return self._start_execution(params)

    # --- subtitle_processing ---
    def asr_speech_to_text_task(
        self, type: str, video: str, space_name: str, language: Optional[str] = None
    ) -> Dict[str, Any]:
        media_input = self._build_media_input(type, video, space_name)
        ask: Dict[str, Any] = {"WithSpeakerInfo": True}
        if language:
            ask["Language"] = language
        params = {
            "Input": media_input,
            "Operation": {"Type": "Task", "Task": {"Type": "Asr", "Asr": ask}},
        }
        return self._start_execution(params)

    def ocr_text_to_subtitles_task(
        self, type: str, video: str, space_name: str
    ) -> Dict[str, Any]:
        media_input = self._build_media_input(type, video, space_name)
        params = {
            "Input": media_input,
            "Operation": {"Type": "Task", "Task": {"Type": "Ocr", "Ocr": {}}},
        }
        return self._start_execution(params)

    def video_subtitles_removal_task(
        self, type: str, video: str, space_name: str
    ) -> Dict[str, Any]:
        media_input = self._build_media_input(type, video, space_name)
        params = {
            "Input": media_input,
            "Operation": {
                "Type": "Task",
                "Task": {
                    "Type": "Erase",
                    "Erase": {
                        "Mode": "Auto",
                        "NewVid": True,
                        "Auto": {"Type": "Subtitle"},
                    },
                },
            },
        }
        return self._start_execution(params)

    # --- video_enhancement ---
    def video_quality_enhancement_task(
        self, type: str, video: str, space_name: str
    ) -> Dict[str, Any]:
        media_input = self._build_media_input(type, video, space_name)
        params = {
            "Input": media_input,
            "Operation": {
                "Type": "Task",
                "Task": {
                    "Type": "Enhance",
                    "Enhance": {
                        "Type": "Moe",
                        "MoeEnhance": {
                            "Config": "short_series",
                            "VideoStrategy": {"RepairStyle": 1, "RepairStrength": 0},
                        },
                    },
                },
            },
        }
        return self._start_execution(params)

    def video_super_resolution_task(
        self,
        type: str,
        video: str,
        space_name: str,
        Res: Optional[str] = None,
        ResLimit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        - type(str)：** 必选字段 **，文件类型，默认值为 `Vid` 。字段取值如下
            - Vid
            - DirectUrl
        - video： ** 必选字段 **,  视频文件信息, 当 type 为 `Vid` 时， video 为视频文件 ID；当 type 为 `DirectUrl` 时， video 为 FileName
        - space_name(str)： ** 必选字段 **,  视频空间名称
        - Res(str): ** 必选字段 ** 目标分辨率。支持的取值如下所示。
            - 240p
            - 360p
            - 480p
            - 540p
            - 720p
            - 1080p
            - 2k
            - 4k
        - ResLimit(int): ** 必选字段 ** 目标长宽限制，用于指定输出视频的长边或短边的最大像素值，取值范围为 [64, 2160]。
        """
        valid_res = {"240p", "360p", "480p", "540p", "720p", "1080p", "2k", "4k"}
        if Res is not None and Res not in valid_res:
            raise ValueError(f"Res must be one of {sorted(valid_res)}, but got {Res}")
        if ResLimit is not None and (
            not isinstance(ResLimit, int) or ResLimit < 64 or ResLimit > 2160
        ):
            raise ValueError("ResLimit must be an int in [64, 2160]")
        if Res is not None and ResLimit is not None:
            raise ValueError("Res and ResLimit cannot both be set")
        media_input = self._build_media_input(type, video, space_name)
        target: Dict[str, Any] = {}
        if ResLimit is not None:
            target = {"ResLimit": ResLimit}
        if Res is not None:
            target = {"Res": Res}
        params = {
            "Input": media_input,
            "Operation": {
                "Type": "Task",
                "Task": {
                    "Type": "Enhance",
                    "Enhance": {
                        "Type": "Moe",
                        "MoeEnhance": {
                            "Config": "common",
                            "Target": target,
                            "VideoStrategy": {"RepairStyle": 1, "RepairStrength": 0},
                        },
                    },
                },
            },
        }
        return self._start_execution(params)

    def video_interlacing_task(
        self, type: str, video: str, space_name: str, Fps: float
    ) -> Dict[str, Any]:
        if not isinstance(Fps, (int, float)) or Fps <= 0 or Fps > 120:
            raise ValueError("Fps must be > 0 and <= 120")
        media_input = self._build_media_input(type, video, space_name)
        params = {
            "Input": media_input,
            "Operation": {
                "Type": "Task",
                "Task": {
                    "Type": "Enhance",
                    "Enhance": {
                        "Type": "Moe",
                        "MoeEnhance": {
                            "Config": "common",
                            "Target": {"Fps": Fps},
                            "VideoStrategy": {"RepairStyle": 1, "RepairStrength": 0},
                        },
                    },
                },
            },
        }
        return self._start_execution(params)

    # ----------------------------
    # upload tools (ported from mcp_tools/upload.py, without pb SDK)
    # ----------------------------
    def video_batch_upload(
        self, space_name: str, urls: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        从公网 URL 批量拉取音视频/图片上传到点播空间（异步任务）。

        对应 OpenAPI：
        - Action: UploadMediaByUrl
        - Version: 2020-08-01
        """
        if not space_name or not isinstance(space_name, str) or not space_name.strip():
            raise ValueError("video_batch_upload: space_name is required")
        if not urls or not isinstance(urls, list):
            raise ValueError("video_batch_upload: urls must be a non-empty list")

        url_sets: List[Dict[str, str]] = []
        for u in urls:
            if not isinstance(u, dict):
                raise TypeError("video_batch_upload: each url item must be a dict")
            source_url = u.get("SourceUrl", "")
            file_ext = u.get("FileExtension", "")
            if not source_url:
                raise ValueError("video_batch_upload: SourceUrl is required")
            if not file_ext or not file_ext.startswith("."):
                raise ValueError(
                    "video_batch_upload: FileExtension must start with '.'"
                )
            # 使用 UUID 作为 FileName，避免原 URL 含特殊字符/中文等导致异常
            url_sets.append(
                {
                    "SourceUrl": source_url,
                    "FileExtension": file_ext,
                    "FileName": f"{uuid.uuid4().hex}{file_ext}",
                }
            )

        resp = self._post(
            "UploadMediaByUrl", {"SpaceName": space_name, "URLSets": url_sets}
        )
        result = resp.get("Result", {}) if isinstance(resp, dict) else {}
        data = result.get("Data", []) or []
        job_ids: List[str] = []
        for item in data:
            if isinstance(item, dict) and item.get("JobId"):
                job_ids.append(item["JobId"])
        return {"JobIds": job_ids}

    def query_batch_upload_task_info(self, job_ids: str) -> Dict[str, Any]:
        """
        查询 URL 批量上传任务状态。

        对应 OpenAPI：
        - Action: QueryUploadTaskInfo
        - Version: 2020-08-01
        """
        if not job_ids or not isinstance(job_ids, str) or not job_ids.strip():
            raise ValueError("query_batch_upload_task_info: job_ids is required")

        resp = self._get("QueryUploadTaskInfo", params={"JobIds": job_ids})
        result = resp.get("Result", {}) if isinstance(resp, dict) else {}
        data = result.get("Data", {}) or {}
        media_info_list = data.get("MediaInfoList", []) or []

        urls_out: List[Dict[str, Any]] = []
        for item in media_info_list:
            if not isinstance(item, dict):
                continue
            state = item.get("State", "")
            space_name = item.get("SpaceName", "")
            vid = item.get("Vid", "")
            source_info = item.get("SourceInfo", {}) or {}
            file_name = source_info.get("FileName", "")

            url_info: Dict[str, Any] = {
                "Vid": vid,
                "DirectUrl": file_name,
                "RequestId": item.get("RequestId", ""),
                "JobId": item.get("JobId", ""),
                "State": state,
                "SpaceName": space_name,
            }
            if state == "success" and space_name and file_name:
                url_info["Url"] = self.get_play_url("directurl", file_name, space_name)
            urls_out.append(url_info)

        return {"Urls": urls_out}

    # ----------------------------
    # hybrid upload: URL or local file
    # ----------------------------
    def upload_media_auto(
        self, source: str, space_name: Optional[str] = None, file_ext: str = ".mp4"
    ) -> Dict[str, Any]:
        """
        根据 source 自动选择上传方式：
        - 以 http(s):// 开头：URL 上传（UploadMediaByUrl），返回 type=url + JobIds
        - 否则：本地文件上传（ApplyUploadInfo + TOS 直传/分片 + CommitUploadInfo），返回 type=local + Vid/DirectUrl 等
        """
        if not source or not isinstance(source, str):
            raise ValueError("upload_media_auto: source is required")

        if not space_name:
            space_name = os.getenv("VOLC_SPACE_NAME", "").strip()
        if not space_name:
            raise ValueError(
                "upload_media_auto: VOLC_SPACE_NAME must be set or passed explicitly"
            )

        if source.startswith(("http://", "https://")):
            resp = self.video_batch_upload(
                space_name, [{"SourceUrl": source, "FileExtension": file_ext}]
            )
            return {
                "type": "url",
                "JobIds": resp.get("JobIds", []),
                "raw": resp,
            }

        p = Path(source)
        if not p.is_file():
            raise ValueError(f"upload_media_auto: local file not found: {source}")

        file_path = str(p)
        file_size = p.stat().st_size
        file_name = f"{uuid.uuid4().hex}{file_ext}"
        storage_class = STORAGE_STANDARD
        chunk_size = 0

        apply_params: Dict[str, Any] = {
            "SpaceName": space_name,
            "FileSize": file_size,
            "FileType": "",
            "FileName": file_name,
            "FileExtension": file_ext,
            "StorageClass": storage_class,
            "ClientNetWorkMode": "",
            "ClientIDCMode": "",
            "NeedFallback": True,
            "UploadHostPrefer": "",
        }
        apply_resp = self._get("ApplyUploadInfo", apply_params)
        raise_for_vod_response(apply_resp)
        apply_data = result_data(apply_resp)
        session_key = upload_tob_from_apply_data(
            self._tos_uploader, apply_data, file_path, storage_class, chunk_size
        )

        commit_resp = self._get(
            "CommitUploadInfo", {"SpaceName": space_name, "SessionKey": session_key}
        )
        raise_for_vod_response(commit_resp)
        data = result_data(commit_resp)
        return {
            "type": "local",
            "Vid": data.get("Vid"),
            "PosterUri": data.get("PosterUri"),
            "DirectUrl": (data.get("SourceInfo") or {}).get("FileName"),
        }
