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

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from project_paths import get_project_root
from execution_mode import ExecutionMode, resolve_mode, step_log


def _load_skill_env() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    skill_dir = Path(__file__).resolve().parents[1]
    load_dotenv(dotenv_path=skill_dir / ".env", override=False)


_OUTPUT_DIR_OVERRIDE: Path | None = None


def _output_dir() -> Path:
    if _OUTPUT_DIR_OVERRIDE is not None:
        _OUTPUT_DIR_OVERRIDE.mkdir(parents=True, exist_ok=True)
        return _OUTPUT_DIR_OVERRIDE
    out = get_project_root() / "output"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_json(name: str, data: Any) -> Path:
    out_path = _output_dir() / name
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out_path


def _infer_task_name_from_args(args: argparse.Namespace) -> str:
    """
    素材名推导（用于 output/<素材名>/）：
    - URL: 取最后一段去扩展名
    - 本地文件: 取文件名去扩展名
    - DirectUrl: 取 FileName 去扩展名
    - Vid: 取 Vid 值
    """
    # 显式参数优先（跳过上传场景）
    if (args.vid or "").strip():
        return (args.vid or "").strip()
    if (args.directurl or "").strip():
        return Path((args.directurl or "").strip()).stem or "directurl"

    src = (args.source or "").strip()
    if not src:
        return "task"

    lower = src.lower()
    if lower.startswith(("vid://", "directurl://")):
        v = src.split("://", 1)[1].strip()
        if lower.startswith("vid://"):
            return v or "vid"
        return Path(v).stem or "directurl"

    # 兼容直接传 vid（v0xxx）
    if lower.startswith("v0") and len(src) >= 8 and " " not in src and "/" not in src:
        return src

    if lower.startswith(("http://", "https://")):
        from urllib.parse import urlparse, unquote

        path = unquote(urlparse(src).path or "")
        stem = Path(path).stem if path else ""
        return stem or "remote_source"

    # 本地文件路径
    p = Path(src).expanduser()
    return p.stem or "local_source"


def _ensure_default_task_output_dir(
    args: argparse.Namespace, mode: ExecutionMode
) -> None:
    """未传 --output-dir 时，为本次素材处理分配 output/<素材名(_01)>/ 并打印日志。"""
    global _OUTPUT_DIR_OVERRIDE
    if _OUTPUT_DIR_OVERRIDE is not None:
        return

    from output_dir_resolve import output_base, allocate_unique_task_output_dir

    out_root = output_base("")
    task_name = _infer_task_name_from_args(args)
    _OUTPUT_DIR_OVERRIDE = allocate_unique_task_output_dir(
        output_root=out_root, raw_task_name=task_name
    )
    _OUTPUT_DIR_OVERRIDE.mkdir(parents=True, exist_ok=True)

    try:
        rel = _OUTPUT_DIR_OVERRIDE.relative_to(get_project_root())
        print(f"【{mode.value}】未指定 --output-dir，使用任务目录: {rel}")
    except ValueError:
        print(
            f"【{mode.value}】未指定 --output-dir，使用任务目录: {_OUTPUT_DIR_OVERRIDE}"
        )


def _poll_upload(
    api, job_ids: List[str], *, interval_s: float = 5.0, max_attempts: int = 240
) -> List[Dict[str, Any]]:
    joined = ",".join(job_ids)
    for attempt in range(max_attempts):
        resp = api.query_batch_upload_task_info(joined)
        urls = resp.get("Urls", []) if isinstance(resp, dict) else []
        states: Dict[str, int] = {}
        for u in urls:
            st = (u or {}).get("State", "unknown")
            states[st] = states.get(st, 0) + 1
        print(f"[upload] attempt={attempt + 1}/{max_attempts} states={states}")
        done = all(
            (u or {}).get("State") in ("success", "failed") for u in urls
        ) and len(urls) == len(job_ids)
        if done:
            return urls
        time.sleep(interval_s)
    raise TimeoutError("upload polling timeout")


def _poll_vcreative(
    api,
    vcreative_id: str,
    space_name: str,
    *,
    interval_s: float = 5.0,
    max_attempts: int = 240,
) -> Dict[str, Any]:
    last: Dict[str, Any] = {}
    consecutive_errors = 0
    for attempt in range(max_attempts):
        try:
            last = api.get_v_creative_task_result_once(vcreative_id, space_name)
            consecutive_errors = 0
        except Exception as e:
            msg = str(e)
            retryable = (
                "HTTP 5" in msg
                or "downstream service error" in msg.lower()
                or "InternalError" in msg
                or 'CodeN":1000' in msg
            )
            consecutive_errors += 1
            print(
                f"[vcreative] attempt={attempt + 1}/{max_attempts} transient_error={retryable} err={msg[:220]}"
            )
            if not retryable or consecutive_errors >= 12:
                raise
            sleep_s = min(60.0, interval_s * (2 ** min(4, consecutive_errors - 1)))
            time.sleep(sleep_s)
            continue
        status = last.get("Status") if isinstance(last, dict) else None
        print(f"[vcreative] attempt={attempt + 1}/{max_attempts} status={status}")
        if status == "success":
            return last
        if status == "failed_run":
            raise RuntimeError(
                f"vcreative failed: {json.dumps(last, ensure_ascii=False)[:2000]}"
            )
        time.sleep(interval_s)
    raise TimeoutError("vcreative polling timeout")


def _poll_execution(
    api,
    task_type: str,
    run_id: str,
    *,
    interval_s: float = 5.0,
    max_attempts: int = 240,
) -> Dict[str, Any]:
    last: Dict[str, Any] = {}
    consecutive_errors = 0
    for attempt in range(max_attempts):
        try:
            last = api.get_media_execution_task_result(task_type, run_id)
            consecutive_errors = 0
        except Exception as e:
            msg = str(e)
            retryable = (
                "HTTP 5" in msg
                or "downstream service error" in msg.lower()
                or "InternalError" in msg
                or 'CodeN":1000' in msg
            )
            consecutive_errors += 1
            print(
                f"[exec:{task_type}] attempt={attempt + 1}/{max_attempts} transient_error={retryable} err={msg[:220]}"
            )
            if not retryable or consecutive_errors >= 12:
                raise
            sleep_s = min(60.0, interval_s * (2 ** min(4, consecutive_errors - 1)))
            time.sleep(sleep_s)
            continue
        status = last.get("Status") if isinstance(last, dict) else None
        print(
            f"[exec:{task_type}] attempt={attempt + 1}/{max_attempts} status={status}"
        )
        if status == "Success":
            return last
        if status in ("Failed", "Fail", "Error"):
            raise RuntimeError(
                f"execution failed: {json.dumps(last, ensure_ascii=False)[:2000]}"
            )
        time.sleep(interval_s)
    raise TimeoutError(f"execution polling timeout: {task_type}")


def _pick_first_success_upload(urls: List[Dict[str, Any]]) -> Tuple[str, str, str]:
    for u in urls:
        if (u or {}).get("State") == "success":
            space = (u or {}).get("SpaceName") or ""
            vid = (u or {}).get("Vid") or ""
            direct = (u or {}).get("DirectUrl") or ""
            if space and vid:
                return space, vid, direct
    raise RuntimeError("no successful upload item found")


def _normalize_preuploaded_source(source: str) -> Tuple[str, str]:
    s = (source or "").strip()
    if not s:
        raise ValueError("empty source")
    lower = s.lower()
    if lower.startswith("vid://"):
        return "Vid", s.split("://", 1)[1]
    if lower.startswith("directurl://"):
        return "DirectUrl", s.split("://", 1)[1]
    if lower.startswith("v0") and len(s) >= 8 and " " not in s and "/" not in s:
        return "Vid", s
    return "DirectUrl", s


# ═════════════════════════════════════════════════════════════
# Local 模式实现：全部在本地执行，无需上传/空间/云端服务
# ═════════════════════════════════════════════════════════════


def _ensure_local_deps() -> None:
    """检查 local 模式依赖是否已安装，未安装则自动安装 requirements-local.txt。
    使用标记文件 + requirements-local.txt 时间戳比对跳过已安装的情况。"""
    scripts_dir = Path(__file__).resolve().parent
    req_file = scripts_dir / "requirements-local.txt"
    venv_dir = scripts_dir / ".venv"
    marker = (
        venv_dir / ".deps_local_installed"
        if venv_dir.is_dir()
        else scripts_dir / ".deps_local_installed"
    )

    if marker.exists():
        if not req_file.exists() or marker.stat().st_mtime >= req_file.stat().st_mtime:
            print("[local] 本地依赖已安装，跳过")
            return

    probe_packages = [
        ("imageio_ffmpeg", "imageio-ffmpeg"),
        ("demucs", "demucs"),
        ("soundfile", "soundfile"),
        ("torch", "torch"),
        ("numpy", "numpy"),
    ]
    missing = []
    for mod_name, pip_name in probe_packages:
        try:
            __import__(mod_name)
        except ImportError:
            missing.append(pip_name)

    if not missing:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
        return

    print(f"[local] 检测到缺少依赖: {', '.join(missing)}")
    if req_file.exists():
        print("[local] 自动安装 requirements-local.txt ...")
        import subprocess as _sp

        _sp.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
    else:
        import subprocess as _sp

        print(f"[local] 安装缺少的包: {' '.join(missing)} ...")
        _sp.check_call(
            [sys.executable, "-m", "pip", "install"] + missing,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()
    print("[local] 依赖安装完成")


def _run_local(args: argparse.Namespace) -> None:
    """Local 模式：本地文件 → ffmpeg 提取音频 → Demucs 分离 → ffmpeg 降噪 → Qwen-ASR"""
    global _OUTPUT_DIR_OVERRIDE
    mode = ExecutionMode.LOCAL

    # 确保 local 模式依赖已安装（首次切换时自动下载）
    step_log(mode, "step0", "检查本地依赖")
    _ensure_local_deps()

    src = (args.source or "").strip()
    if not src:
        raise ValueError("local 模式必须提供本地文件路径作为 source")

    is_url = src.lower().startswith(("http://", "https://"))

    # 未传 --output-dir 时：按素材名占用 output/<素材名(_01)>/，避免产物全部堆在 output/ 根目录
    _ensure_default_task_output_dir(args, mode)

    source_path = Path(src).expanduser()
    if not source_path.is_file():
        if is_url:
            step_log(mode, "step1", "下载远程文件到本地")
            import urllib.request

            dl_path = _output_dir() / f"source{args.ext}"
            urllib.request.urlretrieve(src, str(dl_path))
            source_path = dl_path
            step_log(mode, "step1", f"下载完成 → {dl_path}")
        else:
            raise ValueError(f"本地文件不存在: {src}")

    # Step 1: 本地文件直接使用，无需上传
    step_log(mode, "step1", f"使用本地文件: {source_path}")
    _write_json(
        "step1_preuploaded.json",
        {
            "AssetType": "LocalFile",
            "AssetValue": str(source_path),
            "LocalPath": str(source_path),
            "PlayURL": str(source_path),
            "_execution_mode": "local",
        },
    )

    import ffmpeg_utils as fu

    # Step 2: 提取音频
    step_log(mode, "step2", "提取音频 (ffmpeg)")
    audio_mp3 = _output_dir() / "extracted_audio.mp3"
    fu.extract_audio(source_path, audio_mp3)
    _write_json(
        "step2_extract_audio_result.json",
        {
            "Status": "success",
            "OutputJson": {"filename": str(audio_mp3)},
            "_execution_mode": "local",
        },
    )
    step_log(mode, "step2", f"提取完成 → {audio_mp3}")

    # Step 3: 人声/背景音分离
    step_log(mode, "step3", "人声/背景音分离 (Demucs)")
    from local_av_separation import separate_voice_background

    sep_dir = _output_dir() / "separation"
    voice_path, bg_path = separate_voice_background(audio_mp3, sep_dir)
    _write_json(
        "step3_voice_separation_result.json",
        {
            "Status": "Success",
            "AudioUrls": [
                {"Type": "voice", "DirectUrl": str(voice_path), "Url": str(voice_path)},
                {"Type": "background", "DirectUrl": str(bg_path), "Url": str(bg_path)},
            ],
            "_execution_mode": "local",
        },
    )
    step_log(mode, "step3", f"分离完成 → 人声={voice_path} 背景={bg_path}")

    # Step 4: 人声降噪
    step_log(mode, "step4", "人声降噪 (ffmpeg afftdn)")
    denoised_path = _output_dir() / "denoised_voice.mp3"
    try:
        fu.denoise_audio(voice_path, denoised_path, method="afftdn")
        _write_json(
            "step4_denoise_result.json",
            {
                "Status": "Success",
                "VideoUrls": [
                    {"DirectUrl": str(denoised_path), "Url": str(denoised_path)}
                ],
                "_execution_mode": "local",
            },
        )
        step_log(mode, "step4", f"降噪完成 → {denoised_path}")
    except Exception as e:
        print(f"[警告] 降噪失败: {e}，使用原人声文件继续")
        denoised_path = voice_path

    # Step 5: ASR 识别
    step_log(mode, "step5", "ASR 识别 (Qwen3-ASR)")
    _write_json(
        "step5_play_url.json",
        {
            "PlayURL": str(denoised_path),
            "DirectUrl": str(denoised_path),
            "LocalPath": str(denoised_path),
            "_execution_mode": "local",
        },
    )
    from local_asr import transcribe_local

    asr_output_path = _output_dir() / "step5_asr_raw_local.json"
    step_log(mode, "step5", f"ASR 完成 → {asr_output_path}")

    step_log(
        mode,
        "done",
        "ASR 流水线完成。运行 prepare_export_data.py 进行数据预处理，之后可启动审核页或直接导出最终视频。",
    )


# ═════════════════════════════════════════════════════════════
# Cloud / APIG 模式实现（原有逻辑，增加日志前缀）
# ═════════════════════════════════════════════════════════════


def _run_cloud(args: argparse.Namespace, mode: ExecutionMode) -> None:
    """Cloud/APIG 模式：上传 → 提取音频 → 人声分离 → 降噪 → ASR（原流程）"""
    if not args.space:
        args.space = os.getenv("VOLC_SPACE_NAME", "").strip()

    from api_manage import ApiManage
    from asr_volc import transcribe_audio_url

    if not args.space:
        raise ValueError("space_name is required (set VOLC_SPACE_NAME or pass --space)")

    api = ApiManage()
    space_name = args.space

    # 未传 --output-dir 时：按素材名占用 output/<素材名(_01)>/，避免产物全部堆在 output/ 根目录
    _ensure_default_task_output_dir(args, mode)

    # Step 1: 上传 / 识别已有素材
    asset_type = ""
    asset_value = ""
    vid = ""
    directurl = ""

    if (args.vid or "").strip() or (args.directurl or "").strip():
        if (args.vid or "").strip() and (args.directurl or "").strip():
            raise ValueError("不能同时传 --vid 与 --directurl")
        asset_type = "Vid" if (args.vid or "").strip() else "DirectUrl"
        asset_value = (args.vid or args.directurl).strip()
        step_log(mode, "step1", f"跳过上传：使用已存在 {asset_type}={asset_value}")
        _write_json(
            "step1_preuploaded.json",
            {
                "AssetType": asset_type,
                "AssetValue": asset_value,
                "SpaceName": space_name,
            },
        )
    else:
        src = (args.source or "").strip()
        if src.lower().startswith(("vid://", "directurl://")) or (
            src.lower().startswith("v0") and len(src) >= 8
        ):
            asset_type, asset_value = _normalize_preuploaded_source(src)
            step_log(mode, "step1", f"跳过上传：识别为 {asset_type}={asset_value}")
            _write_json(
                "step1_preuploaded.json",
                {
                    "AssetType": asset_type,
                    "AssetValue": asset_value,
                    "SpaceName": space_name,
                },
            )
        else:
            step_log(mode, "step1", "上传素材")
            upload_info = api.upload_media_auto(
                args.source, space_name=space_name, file_ext=args.ext
            )
            _write_json("step1_upload_submit.json", upload_info)
            if upload_info.get("type") == "url":
                step_log(mode, "step1", "URL 上传方式")
                job_ids = upload_info.get("JobIds") or []
                if not job_ids:
                    raise RuntimeError(f"Upload returned empty JobIds: {upload_info}")
                urls = _poll_upload(api, job_ids)
                _write_json("step1_upload_query.json", {"Urls": urls})
                space_name, vid, directurl = _pick_first_success_upload(urls)
            else:
                step_log(mode, "step1", "本地文件上传方式")
                vid = upload_info.get("Vid") or ""
                directurl = upload_info.get("DirectUrl") or ""
                if not vid and not directurl:
                    raise RuntimeError(
                        f"Local upload returned empty Vid/DirectUrl: {upload_info}"
                    )
            step_log(mode, "step1", f"上传成功 Vid={vid} DirectUrl={directurl}")
            asset_type = "Vid" if vid else "DirectUrl"
            asset_value = vid or directurl

    if asset_type == "Vid":
        vid = asset_value
    else:
        directurl = asset_value

    step1_path = _output_dir() / "step1_preuploaded.json"
    step1_data = {}
    if step1_path.is_file():
        step1_data = json.loads(step1_path.read_text(encoding="utf-8"))
    step1_data.update(
        {"AssetType": asset_type, "AssetValue": asset_value, "SpaceName": space_name}
    )
    if asset_type == "Vid":
        step1_data["Vid"] = asset_value
        step1_data["DirectUrl"] = ""
    else:
        step1_data["Vid"] = ""
        step1_data["DirectUrl"] = asset_value
    try:
        step1_data["PlayURL"] = api.get_play_url(
            type=asset_type.lower(),
            source=asset_value,
            space_name=space_name,
            expired_minutes=60,
        )
    except Exception as e:
        print(f"[警告] 获取视频 PlayURL 失败: {e}")
    _write_json("step1_preuploaded.json", step1_data)

    # Step 2: 提取音频
    step_log(mode, "step2", "提取音频")
    extract = api.extract_audio(
        type=asset_type.lower(), source=asset_value, space_name=space_name, format="mp3"
    )
    _write_json("step2_extract_audio_submit.json", extract)
    vcreative_id = extract.get("VCreativeId") or ""
    if not vcreative_id:
        raise RuntimeError(f"extract_audio returned empty VCreativeId: {extract}")
    extract_res = _poll_vcreative(api, vcreative_id, space_name)
    _write_json("step2_extract_audio_result.json", extract_res)
    extracted_filename = ((extract_res.get("OutputJson") or {}).get("filename")) or ""
    step_log(mode, "step2", f"提取音频完成 文件名={extracted_filename}")

    # Step 3: 人声/背景分离
    step_log(mode, "step3", "人声/背景音分离")
    sep = api.voice_separation_task(
        type=asset_type, video=asset_value, space_name=space_name
    )
    _write_json("step3_voice_separation_submit.json", sep)
    run_id = sep.get("RunId") or ""
    if not run_id:
        raise RuntimeError(f"voice_separation_task returned empty RunId: {sep}")
    sep_res = _poll_execution(api, "voiceSeparation", run_id)
    _write_json("step3_voice_separation_result.json", sep_res)

    voice_file = ""
    bg_file = ""
    for a in sep_res.get("AudioUrls", []) or []:
        if (a or {}).get("Type") == "voice":
            voice_file = (a or {}).get("DirectUrl") or ""
        if (a or {}).get("Type") == "background":
            bg_file = (a or {}).get("DirectUrl") or ""
    if not voice_file:
        raise RuntimeError(
            f"voice separation result missing voice DirectUrl: {sep_res}"
        )
    step_log(mode, "step3", f"人声分离完成 人声={voice_file} 背景={bg_file}")

    # Step 4: 人声降噪
    step_log(mode, "step4", "人声降噪")
    denoise_max_retries = 3
    denoised_file = ""
    for attempt in range(1, denoise_max_retries + 1):
        try:
            denoise = api.audio_noise_reduction_task(
                type="DirectUrl", audio=voice_file, space_name=space_name
            )
            _write_json("step4_denoise_submit.json", denoise)
            denoise_run = denoise.get("RunId") or ""
            if not denoise_run:
                raise RuntimeError("audio_noise_reduction_task returned empty RunId")
            denoise_res = _poll_execution(api, "audioNoiseReduction", denoise_run)
            _write_json("step4_denoise_result.json", denoise_res)
            for v in denoise_res.get("VideoUrls", []) or []:
                denoised_file = (v or {}).get("DirectUrl") or ""
                if denoised_file:
                    break
            if not denoised_file:
                raise RuntimeError("denoise result missing DirectUrl")
            step_log(mode, "step4", f"降噪完成 DirectUrl={denoised_file}")
            break
        except Exception as e:
            msg = str(e)
            is_retryable = "500" in msg or "InternalError" in msg.lower()
            if is_retryable and attempt < denoise_max_retries:
                step_log(
                    mode, "step4", f"第 {attempt}/{denoise_max_retries} 次失败，重试..."
                )
                time.sleep(5)
            else:
                print(f"[警告] 降噪失败: {e}，使用原人声文件继续")
                denoised_file = voice_file
                break
    if not denoised_file:
        denoised_file = voice_file

    # Step 5: ASR 识别
    step_log(mode, "step5", "火山 ASR 识别")
    play_url = api.get_play_url(
        type="directurl",
        source=denoised_file,
        space_name=space_name,
        expired_minutes=60,
    )
    _write_json(
        "step5_play_url.json", {"PlayURL": play_url, "DirectUrl": denoised_file}
    )
    rid, asr_res = transcribe_audio_url(
        play_url, audio_type="m4a", output_dir=_output_dir()
    )
    _write_json(f"step5_asr_raw_{rid}.json", asr_res)
    step_log(mode, "step5", f"ASR 转录完成 输出: step5_asr_raw_{rid}.json")


def main() -> None:
    global _OUTPUT_DIR_OVERRIDE
    parser = argparse.ArgumentParser(
        description="URL/本地文件 -> 上传 -> 提取音频 -> 人声/背景 -> 降噪 -> ASR 转录"
    )
    parser.add_argument(
        "source", nargs="?", help="素材来源：支持 http(s) URL 或本地文件路径"
    )
    parser.add_argument("--ext", default=".mp4", help="FileExtension, 默认 .mp4")
    parser.add_argument(
        "--space", default="", help="SpaceName（默认读取 VOLC_SPACE_NAME）"
    )
    parser.add_argument("--vid", default="", help="直接指定 Vid（跳过上传）")
    parser.add_argument(
        "--directurl", default="", help="直接指定 DirectUrl 文件名（跳过上传）"
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="输出目录，默认 output；可指定 output/<文件名> 或 output/<文件名>(01)",
    )
    parser.add_argument(
        "--mode",
        default="",
        help="执行模式: apig / cloud / local（默认自动检测，优先级 apig>cloud>local）",
    )
    args = parser.parse_args()

    if args.output_dir:
        out_str = str(args.output_dir).strip()
        proj_root = get_project_root()
        out_base = (proj_root / "output").resolve()

        cand = Path(out_str)
        if cand.is_absolute():
            resolved = cand.resolve()
            try:
                resolved.relative_to(out_base)
            except ValueError:
                raise SystemExit(
                    f"ERROR: --output-dir 必须在 {out_base} 下：{resolved}"
                )
            _OUTPUT_DIR_OVERRIDE = resolved
        else:
            if not out_str.startswith("output/"):
                raise SystemExit(
                    "ERROR: --output-dir 只允许传 `output/<文件名>`（相对路径）"
                )
            resolved = (proj_root / out_str).resolve()
            try:
                resolved.relative_to(out_base)
            except ValueError:
                raise SystemExit(f"ERROR: --output-dir 路径越界：{out_str}")
            _OUTPUT_DIR_OVERRIDE = resolved

        _OUTPUT_DIR_OVERRIDE.mkdir(parents=True, exist_ok=True)
    else:
        _OUTPUT_DIR_OVERRIDE = None

    if not args.source and not (
        (getattr(args, "vid", "") or "").strip()
        or (getattr(args, "directurl", "") or "").strip()
    ):
        raise ValueError(
            "缺少 source：请提供素材 URL/本地路径，或使用 --vid / --directurl 跳过上传。"
        )

    _load_skill_env()

    # 解析执行模式
    mode = resolve_mode(args.mode if args.mode else None)
    print(f"\n{'=' * 60}")
    print(f"  执行模式: {mode.value}")
    print(f"{'=' * 60}\n")

    # Step2 Gate：未完成配置确认禁止进入 Step3
    # - 若未传 --output-dir，则先为本次素材分配任务目录并打印，便于用户用同一目录执行 step2_confirm_config.py
    _ensure_default_task_output_dir(args, mode)
    step2_ckpt = _output_dir() / "step2_config_confirmed.json"
    if not step2_ckpt.is_file():
        print("=" * 60)
        print(
            "⚠️  检测到 Step2 未确认（缺少 step2_config_confirmed.json），已阻断进入 Step3。"
        )
        print()
        try:
            rel = _output_dir().relative_to(get_project_root())
            print(f"请先完成 Step2，并在同一输出目录生成 checkpoint：{rel}")
        except ValueError:
            print(f"请先完成 Step2，并在同一输出目录生成 checkpoint：{_output_dir()}")
        print()
        print("执行命令：")
        print(
            f'  cd {Path(__file__).resolve().parent} && python step2_confirm_config.py --output-dir "{_output_dir()}"'
        )
        print("=" * 60)
        raise SystemExit(1)

    if mode == ExecutionMode.LOCAL:
        _run_local(args)
    else:
        # 前置校验（cloud/apig 需要 source 格式正确）
        if args.source and not (
            (args.vid or "").strip() or (args.directurl or "").strip()
        ):
            src = (args.source or "").strip()
            if not src.lower().startswith(("vid://", "directurl://")) and not (
                src.lower().startswith("v0") and len(src) >= 8
            ):
                if src.lower().startswith(("http://", "https://")):
                    pass
                elif "://" in src:
                    raise ValueError(
                        f"URL 必须以 http:// 或 https:// 开头，当前: {src[:50]}..."
                    )
                else:
                    p = Path(src)
                    if not p.is_file():
                        raise ValueError(
                            f"本地文件不存在: {src}，请确认路径正确或使用 http(s):// 开头的 URL"
                        )
        _run_cloud(args, mode)


if __name__ == "__main__":
    main()
