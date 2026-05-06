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
from log_utils import log
from vod_api_constants import (
    VOD_ACTION_APPLY_UPLOAD_INFO,
    VOD_ACTION_COMMIT_UPLOAD_INFO,
    VOD_ACTION_DESCRIBE_DOMAIN_CONFIG,
    VOD_ACTION_GET_AI_CLIP_TASK_RESULT,
    VOD_ACTION_GET_EXECUTION,
    VOD_ACTION_GET_STORAGE_CONFIG,
    VOD_FIELD_AI_CLIP_TASK_ID,
    VOD_ACTION_GET_VIDEO_PLAY_INFO,
    VOD_ACTION_LIST_DOMAIN,
    VOD_ACTION_LIST_SPACE,
    VOD_ACTION_QUERY_UPLOAD_TASK_INFO,
    VOD_ACTION_START_EXECUTION,
    VOD_ACTION_SUBMIT_ASYNC_AI_CLIP,
    VOD_ACTION_UPDATE_MEDIA_PUBLISH_STATUS,
    VOD_ACTION_UPLOAD_MEDIA_BY_URL,
    VOD_ACTION_SUBMIT_AI_TRANSLATION_WORKFLOW,
    VOD_ACTION_GET_AI_TRANSLATION_PROJECT,
    VOD_ACTION_LIST_AI_TRANSLATION_PROJECT,
    VOD_ACTION_CREATE_DRAMA_RECAP_TASK,
    VOD_ACTION_QUERY_DRAMA_RECAP_TASK,
    VOD_ACTION_CREATE_DRAMA_SCRIPT_TASK,
    VOD_ACTION_QUERY_DRAMA_SCRIPT_TASK,
    VOD_ACTION_GET_MEDIA_INFOS,
)

# 按优先级逐级尝试加载 .env（override=False：系统环境变量更优先）
for base in [
    os.getcwd(),
    os.path.dirname(os.path.abspath(__file__)),
    os.path.expanduser("~"),
]:
    env_path = os.path.join(base, ".env")
    if os.path.isfile(env_path):
        load_dotenv(env_path, override=False)
        log(f"已加载 .env：{env_path}")
        break


class ApiManage:
    _VOD_VERSIONS: Dict[str, str] = {
        VOD_ACTION_LIST_SPACE: "2021-01-01",
        VOD_ACTION_UPLOAD_MEDIA_BY_URL: "2020-08-01",
        VOD_ACTION_QUERY_UPLOAD_TASK_INFO: "2020-08-01",
        VOD_ACTION_SUBMIT_ASYNC_AI_CLIP: "2018-01-01",
        VOD_ACTION_GET_AI_CLIP_TASK_RESULT: "2018-01-01",
        VOD_ACTION_GET_VIDEO_PLAY_INFO: "2018-01-01",
        VOD_ACTION_UPDATE_MEDIA_PUBLISH_STATUS: "2020-08-01",
        VOD_ACTION_START_EXECUTION: "2025-01-01",
        VOD_ACTION_GET_EXECUTION: "2025-01-01",
        VOD_ACTION_LIST_DOMAIN: "2023-01-01",
        VOD_ACTION_DESCRIBE_DOMAIN_CONFIG: "2023-07-01",
        VOD_ACTION_GET_STORAGE_CONFIG: "2023-07-01",
        VOD_ACTION_APPLY_UPLOAD_INFO: "2022-01-01",
        VOD_ACTION_COMMIT_UPLOAD_INFO: "2022-01-01",
        VOD_ACTION_SUBMIT_AI_TRANSLATION_WORKFLOW: "2025-01-01",
        VOD_ACTION_GET_AI_TRANSLATION_PROJECT: "2025-01-01",
        VOD_ACTION_LIST_AI_TRANSLATION_PROJECT: "2025-01-01",
        VOD_ACTION_CREATE_DRAMA_RECAP_TASK: "2025-03-03",
        VOD_ACTION_QUERY_DRAMA_RECAP_TASK: "2025-03-03",
        VOD_ACTION_CREATE_DRAMA_SCRIPT_TASK: "2025-03-03",
        VOD_ACTION_QUERY_DRAMA_SCRIPT_TASK: "2025-03-03",
        VOD_ACTION_GET_MEDIA_INFOS: "2023-07-01",
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
            response = self._get(VOD_ACTION_LIST_SPACE)
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
            VOD_ACTION_DESCRIBE_DOMAIN_CONFIG,
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
                VOD_ACTION_LIST_DOMAIN,
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
        reqs = self._get(
            VOD_ACTION_GET_STORAGE_CONFIG, params={"SpaceName": space_name}
        )
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
                VOD_ACTION_UPDATE_MEDIA_PUBLISH_STATUS,
                {"Vid": vid, "Status": publish_status},
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
            VOD_ACTION_GET_VIDEO_PLAY_INFO,
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
    # AI 视频智剪异步任务（ported from mcp_tools/edit.py）
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

    def _submit_async_ai_clip_task(
        self, uploader_space: str, workflow_id: str, param_obj: Dict[str, Any]
    ) -> Dict[str, Any]:
        payload = {
            "ParamObj": param_obj,
            "Uploader": uploader_space,
            "WorkflowId": workflow_id,
        }
        resp = self._post(VOD_ACTION_SUBMIT_ASYNC_AI_CLIP, payload)
        result = resp.get("Result", {}) if isinstance(resp, dict) else {}
        base_resp = result.get("BaseResp", {}) or {}
        tid = (
            result.get(VOD_FIELD_AI_CLIP_TASK_ID, "")
            if isinstance(result, dict)
            else ""
        )
        return {
            VOD_FIELD_AI_CLIP_TASK_ID: tid,
            "Code": result.get("Code"),
            "StatusMessage": base_resp.get("StatusMessage", ""),
            "StatusCode": base_resp.get("StatusCode", 0),
        }

    def get_v_creative_task_result_once(
        self, task_id: str, space_name: Optional[str] = None
    ) -> Dict[str, Any]:
        if not task_id or not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("get_v_creative_task_result: task_id is required")
        if not space_name:
            space_name = os.getenv("VOLC_SPACE_NAME")
        if not space_name or not isinstance(space_name, str) or not space_name.strip():
            raise ValueError("get_v_creative_task_result: space_name is required")

        reqs = self._get(
            VOD_ACTION_GET_AI_CLIP_TASK_RESULT,
            params={VOD_FIELD_AI_CLIP_TASK_ID: task_id, "SpaceName": space_name},
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
        task_id: str,
        space_name: Optional[str] = None,
        interval: float = 2.0,
        max_retries: int = 10,
    ) -> Dict[str, Any]:
        # 同步轮询版本（原 MCP 实现会通过 ctx.report_progress 异步上报，这里移除）。
        last: Optional[Dict[str, Any]] = None
        for _ in range(max_retries):
            last = self.get_v_creative_task_result_once(task_id, space_name)
            status = last.get("Status") if isinstance(last, dict) else None
            if status in ("success", "failed_run"):
                return last
            if status == "running":
                return last
            time.sleep(interval)
        return last or {}

    # ----------------------------
    # StartExecution/GetExecution tools (ported from mcp_tools/* + utils/transcode.py)
    # ----------------------------
    # 说明：这类工具走「媒体处理执行引擎」，启动用 StartExecution，查询用 GetExecution，

    @staticmethod
    def _build_media_input(
        asset_type: str, asset_value: str, space_name: str
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
        resp = self._post(VOD_ACTION_START_EXECUTION, payload)
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
            "highlight",
        }
        if type not in valid_types:
            raise ValueError(
                f"type must be one of {sorted(valid_types)}, but got {type}"
            )
        if not run_id or not run_id.strip():
            raise ValueError("runId must be provided")

        response = self._get(VOD_ACTION_GET_EXECUTION, params={"RunId": run_id})
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
        elif type == "highlight":
            highlight = output.get("Highlight", {}) or {}
            edits = highlight.get("Edits", []) or []
            if isinstance(edits, list):
                for idx, edit in enumerate(edits):
                    if not isinstance(edit, dict):
                        continue
                    file_name = edit.get("FileName", "") or ""
                    vid_ = edit.get("Vid", "") or ""
                    if not file_name:
                        continue
                    video_urls.append(
                        {
                            "DirectUrl": file_name,
                            "Vid": vid_,
                            "Type": "highlight",
                            "Index": idx,
                            "Url": self.get_play_url(
                                "directurl", file_name, space_name
                            ),
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
            VOD_ACTION_UPLOAD_MEDIA_BY_URL,
            {"SpaceName": space_name, "URLSets": url_sets},
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

        resp = self._get(VOD_ACTION_QUERY_UPLOAD_TASK_INFO, params={"JobIds": job_ids})
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
        apply_resp = self._get(VOD_ACTION_APPLY_UPLOAD_INFO, apply_params)
        raise_for_vod_response(apply_resp)
        apply_data = result_data(apply_resp)
        session_key = upload_tob_from_apply_data(
            self._tos_uploader, apply_data, file_path, storage_class, chunk_size
        )

        commit_resp = self._get(
            VOD_ACTION_COMMIT_UPLOAD_INFO,
            {"SpaceName": space_name, "SessionKey": session_key},
        )
        raise_for_vod_response(commit_resp)
        data = result_data(commit_resp)
        return {
            "type": "local",
            "Vid": data.get("Vid"),
            "PosterUri": data.get("PosterUri"),
            "DirectUrl": (data.get("SourceInfo") or {}).get("FileName"),
        }

    # ----------------------------
    # AI 视频翻译 (Translation)
    # ----------------------------
    def submit_ai_translation_workflow(self, body):
        """提交 AI 视频翻译任务。"""
        resp = self._post(VOD_ACTION_SUBMIT_AI_TRANSLATION_WORKFLOW, body)
        return resp

    def get_ai_translation_project(self, params):
        """查询 AI 视频翻译项目详情。"""
        return self._get(VOD_ACTION_GET_AI_TRANSLATION_PROJECT, params=params)

    def list_ai_translation_project(self, params):
        """查询 AI 视频翻译项目列表。"""
        return self._get(VOD_ACTION_LIST_AI_TRANSLATION_PROJECT, params=params)

    # ----------------------------
    # AI 解说视频生成 (Drama Recap)
    # ----------------------------
    def create_drama_recap_task(self, body):
        """提交 AI 解说视频生成任务。"""
        return self._post(VOD_ACTION_CREATE_DRAMA_RECAP_TASK, body)

    def query_drama_recap_task(self, params):
        """查询 AI 解说视频生成任务状态。"""
        return self._get(VOD_ACTION_QUERY_DRAMA_RECAP_TASK, params=params)

    # ----------------------------
    # AI 剧本还原 (Drama Script)
    # ----------------------------
    def create_drama_script_task(self, body):
        """提交 AI 剧本还原任务。"""
        return self._post(VOD_ACTION_CREATE_DRAMA_SCRIPT_TASK, body)

    def query_drama_script_task(self, params):
        """查询 AI 剧本还原任务状态。"""
        return self._get(VOD_ACTION_QUERY_DRAMA_SCRIPT_TASK, params=params)

    # ----------------------------
    # 媒资信息查询 (GetMediaInfos)
    # ----------------------------
    def get_media_infos(self, vids, space_name):
        """查询媒资信息（支持逗号分隔多个 Vid，单次最多 20 个）。"""
        return self._get(
            VOD_ACTION_GET_MEDIA_INFOS, params={"Vids": vids, "SpaceName": space_name}
        )

    # ══════════════════════════════════════════════════════
    # 高层业务方法（从 vod_common.py 迁入）
    # ══════════════════════════════════════════════════════

    # ── 轮询配置 ──────────────────────────────────────
    POLL_INTERVAL = float(os.environ.get("VOD_POLL_INTERVAL", "5"))
    POLL_MAX = int(os.environ.get("VOD_POLL_MAX", "360"))  # 360×5s = 30 分钟
    MAX_VIDEO_DURATION_SECONDS = 600  # 10 分钟

    # ── 播放 URL 便捷方法 ─────────────────────────────

    def get_play_url_by_filename(
        self, space_name: str, file_name: str, expired_minutes: int = 60
    ) -> str:
        """通过 FileName 获取播放链接（对 get_play_url 的便捷包装）。"""
        if not file_name:
            return ""
        try:
            return self.get_play_url(
                "directurl", file_name, space_name, expired_minutes
            )
        except Exception as e:
            from log_utils import log

            log(f"get_play_url_by_filename 失败（{file_name}）: {e}")
            return ""

    # ── 编辑类轮询 ────────────────────────────────────

    def poll_vcreative(self, task_id: str, space_name: str) -> dict:
        """
        轮询编辑类任务，终态：Status == "success" 或 "failed_run"。
        """
        from log_utils import log

        for i in range(1, self.POLL_MAX + 1):
            log(f"轮询编辑任务 [{i}/{self.POLL_MAX}] task_id={task_id}")
            try:
                result = self.get_v_creative_task_result_once(task_id, space_name)
            except Exception as e:
                log(f"  查询异常: {e}")
                time.sleep(self.POLL_INTERVAL)
                continue

            status = result.get("Status", "")

            if status == "success":
                output_json = result.get("OutputJson", {})
                if isinstance(output_json, str):
                    try:
                        output_json = json.loads(output_json)
                    except Exception:
                        output_json = {}
                return {
                    "Status": "success",
                    "OutputJson": output_json,
                }

            if status == "failed_run":
                return {"Status": "failed_run", "detail": result}

            time.sleep(self.POLL_INTERVAL)

        return {
            "error": f"轮询超时（{self.POLL_MAX} 次 × {self.POLL_INTERVAL}s），任务仍在处理中",
            "resume_hint": {
                "description": "任务尚未完成，可用以下命令重启轮询",
                "command": f"python <SKILL_DIR>/scripts/poll_vcreative.py '{task_id}' {space_name}",
            },
        }

    # ── 媒体类轮询 ────────────────────────────────────

    def poll_media(self, task_type: str, run_id: str, space_name: str) -> dict:
        """
        轮询媒体处理任务。循环调用 get_media_execution_task_result 直到终态。
        """
        from log_utils import log

        PENDING_STATUSES = {"", "PendingStart", "Running"}
        TERMINAL_FAIL = {"Failed", "Terminated"}

        sp = space_name
        for i in range(1, self.POLL_MAX + 1):
            log(
                f"轮询媒体任务 [{i}/{self.POLL_MAX}] type={task_type} RunId={run_id} ..."
            )
            try:
                result = self.get_media_execution_task_result(task_type, run_id)
            except Exception as e:
                log(f"  查询异常: {e}")
                time.sleep(self.POLL_INTERVAL)
                continue

            status = result.get("Status", "")
            sp = result.get("SpaceName", space_name)

            if status in PENDING_STATUSES:
                log(f"  状态={status!r}，等待 {self.POLL_INTERVAL}s ...")
                time.sleep(self.POLL_INTERVAL)
                continue

            if status in TERMINAL_FAIL:
                ret = {
                    "Status": status,
                    "Code": result.get("Code", ""),
                    "SpaceName": sp,
                }
                if status == "Failed":
                    ret["resume_hint"] = {
                        "description": "任务执行失败，可检查参数后重新提交，或用以下命令重启轮询",
                        "command": f"python <SKILL_DIR>/scripts/poll_media.py '{task_type}' '{run_id}' {sp}",
                    }
                else:
                    ret["note"] = "任务已被终止，请重新提交任务"
                return ret

            if status == "Success":
                return result

            log(f"  未知状态={status!r}，继续等待 ...")
            time.sleep(self.POLL_INTERVAL)

        return {
            "error": f"轮询超时（{self.POLL_MAX} 次 × {self.POLL_INTERVAL}s），任务仍在处理中",
            "resume_hint": {
                "description": "任务尚未完成，可用以下命令重启轮询",
                "command": f"python <SKILL_DIR>/scripts/poll_media.py '{task_type}' '{run_id}' {sp}",
            },
        }

    # ── 一步提交 + 轮询 ──────────────────────────────

    def submit_vcreative(
        self, workflow_id: str, param_obj: dict, space_name: str
    ) -> dict:
        """提交 AI 视频智剪异步任务，解析任务 ID，自动轮询到终态。"""
        from log_utils import bail, log

        try:
            resp = self._submit_async_ai_clip_task(space_name, workflow_id, param_obj)
        except Exception as e:
            bail(f"提交任务失败：{e}")

        sc = resp.get("StatusCode", 0)
        if sc != 0:
            bail(f"提交任务失败：StatusCode={sc} msg={resp.get('StatusMessage', '')}")

        task_id = resp.get(VOD_FIELD_AI_CLIP_TASK_ID, "")
        if not task_id:
            bail(f"提交任务未返回任务 ID，原始响应：{json.dumps(resp)}")

        log(f"任务已提交，task_id={task_id}，开始轮询...")
        return self.poll_vcreative(task_id, space_name)

    def submit_media(self, params: dict, task_type: str, space_name: str) -> dict:
        """提交 StartExecution，解析 RunId，自动轮询到终态。"""
        from log_utils import bail, log

        try:
            resp = self._start_execution(params)
        except Exception as e:
            bail(f"提交任务失败：{e}")

        run_id = resp.get("RunId", "")
        if not run_id:
            bail(f"提交任务未返回 RunId，原始响应：{json.dumps(resp)}")

        log(f"任务已提交，RunId={run_id}，开始轮询...")
        return self.poll_media(task_type, run_id, space_name)

    # ── 媒资信息辅助 ──────────────────────────────────

    def sum_media_info_list_duration_seconds(self, vid: str, space_name: str):
        """
        调用 GetMediaInfos，对 MediaInfoList 中所有条目的时长求和（秒）。
        若 MediaInfoList 缺失或为空，返回 None。
        """
        raw = self.get_media_infos(vid, space_name)
        result = raw.get("Result", {}) if isinstance(raw, dict) else {}
        media_info_list = result.get("MediaInfoList", [])
        if not media_info_list:
            return None
        total = 0.0
        for item in media_info_list:
            if not isinstance(item, dict):
                continue
            basic_info = item.get("BasicInfo", {}) or {}
            d = basic_info.get("Duration", 0)
            if not d:
                source_info = item.get("SourceInfo", {}) or {}
                d = source_info.get("Duration", 0)
            if d:
                total += float(d)
        return total

    def check_video_duration(self, vid: str, space_name: str):
        """
        校验视频时长是否 ≤ 10 分钟（600 秒）。超限时调用 bail() 终止脚本。
        """
        from log_utils import bail, log

        try:
            duration = self.vid.sum_media_info_list_duration_seconds(space_name)
            if duration is None:
                log(f"警告：未查询到 Vid={vid} 的媒资信息，跳过时长校验")
                return
            if duration > self.MAX_VIDEO_DURATION_SECONDS:
                minutes = duration / 60
                bail(
                    f"视频时长合计 {minutes:.1f} 分钟，超过限制（最大 10 分钟）。"
                    f"请裁剪视频后重新上传。"
                )
            log(
                f"视频时长校验通过：合计 {duration:.1f}s（上限 {self.MAX_VIDEO_DURATION_SECONDS}s）"
            )
        except SystemExit:
            raise
        except Exception as e:
            log(f"警告：视频时长校验失败（{e}），继续执行")
