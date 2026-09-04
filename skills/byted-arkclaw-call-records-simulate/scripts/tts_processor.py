#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""基于 edge-tts 的通话记录合成工具。

读取符合 schema 的通话记录 JSON，按 conversations 顺序逐句合成 MP3 并拼接为单一文件。

用法:
    python scripts/tts_processor.py --material materials/xxx.json [--output ./output]
"""

import argparse
import asyncio
import json
import random
import re
import sys
from pathlib import Path

import edge_tts


REQUIRED_CONV_KEYS = {"role", "text", "voice"}
REQUIRED_TOP_KEYS = {"name", "output_file", "conversations"}
PHONE_PREFIXES = ("13", "15", "17", "18", "19")
FEMALE_VOICE_HINTS = ("Xiaoxiao", "Xiaoyi", "Xiaochen", "Xiaohan", "Xiaomeng")
MALE_VOICE_HINTS = ("Yunxi", "Yunyang", "Yunjian", "Yunhao", "Yunze")


def _validate_material(material: dict, json_path: Path) -> None:
    missing = REQUIRED_TOP_KEYS - material.keys()
    if missing:
        raise ValueError(f"素材 {json_path} 缺少顶层字段: {sorted(missing)}")
    convs = material["conversations"]
    if not isinstance(convs, list) or not convs:
        raise ValueError(f"素材 {json_path} 的 conversations 必须为非空列表")
    for idx, conv in enumerate(convs):
        miss = REQUIRED_CONV_KEYS - conv.keys()
        if miss:
            raise ValueError(
                f"素材 {json_path} conversations[{idx}] 缺少字段: {sorted(miss)}"
            )
        if not conv["text"].strip():
            raise ValueError(f"素材 {json_path} conversations[{idx}].text 为空")


def _generate_virtual_phone_filename() -> str:
    prefix = random.choice(PHONE_PREFIXES)
    suffix = "".join(random.choices("0123456789", k=9))
    return f"{prefix}{suffix}"


def _infer_gender(role: str, voice: str) -> str:
    if re.search(r"(女士|小姐|女生|女性|女)", role):
        return "female"
    if re.search(r"(先生|男生|男性|男)", role):
        return "male"

    for hint in FEMALE_VOICE_HINTS:
        if hint in voice:
            return "female"
    for hint in MALE_VOICE_HINTS:
        if hint in voice:
            return "male"
    return "unknown"


def _extract_callee_name(material: dict) -> str:
    conversations = material.get("conversations", [])
    if len(conversations) >= 2:
        callee = conversations[1]
    elif conversations:
        callee = conversations[-1]
    else:
        callee = {}

    role = callee.get("role", "").strip()
    voice = callee.get("voice", "")
    gender = _infer_gender(role, voice)

    match = re.search(r"[（(]([^）)]+)[）)]", role)
    if match:
        label = re.sub(r"\s+", "", match.group(1))
    else:
        label = re.sub(
            r"^(被叫|候选人|客户|用户|联系人|面试者|接听人|对方)[：:\s-]*",
            "",
            role,
        ).strip()
        label = re.sub(r"\s+", "", label)

    if re.search(r"(女士|先生|小姐)$", label):
        return label
    if re.fullmatch(r"[\u4e00-\u9fff]{1,2}", label):
        if gender == "female":
            return f"{label}女士"
        if gender == "male":
            return f"{label}先生"
        return label
    if label:
        return label
    if gender == "female":
        return "女士"
    if gender == "male":
        return "先生"
    return "未知"


def _normalize_output_file(output_file: str, material: dict) -> str:
    file_name = Path(output_file).name
    callee_name = _extract_callee_name(material)
    if re.fullmatch(rf"1\d{{10}}-{re.escape(callee_name)}\.mp3", file_name):
        return file_name
    return f"{_generate_virtual_phone_filename()}-{callee_name}.mp3"


async def generate_audio_from_json(json_path: str, output_dir: str = "./output") -> str:
    """从通话记录 JSON 合成 MP3 并返回输出路径。"""
    json_file = Path(json_path)
    with open(json_file, "r", encoding="utf-8") as f:
        material = json.load(f)

    _validate_material(material, json_file)

    print(f"📖 正在处理素材: {material['name']}")
    if material.get("duration"):
        print(f"⏱️ 预计时长: {material['duration']}")
    if material.get("scenario"):
        print(f"🏷️ 场景: {material['scenario']}  结果: {material.get('outcome', 'n/a')}")

    final_audio = bytearray()
    total = len(material["conversations"])
    for i, conv in enumerate(material["conversations"], start=1):
        print(f"🎙️ [{i}/{total}] {conv['role']} ({conv['voice']}) ...")
        communicate = edge_tts.Communicate(conv["text"], conv["voice"])
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                final_audio.extend(chunk["data"])

    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    normalized_output_name = _normalize_output_file(material["output_file"], material)
    if normalized_output_name != material["output_file"]:
        print(f"📞 输出文件名已规范为虚拟手机号: {normalized_output_name}")
    output_file = output_dir_path / normalized_output_name
    with open(output_file, "wb") as f:
        f.write(bytes(final_audio))

    size_kb = output_file.stat().st_size / 1024
    print(f"\n✅ 完成！音频文件已保存为: {output_file}  ({size_kb:.1f} KB)")
    return str(output_file)


def main() -> int:
    parser = argparse.ArgumentParser(description="通用通话记录 TTS 合成工具 (edge-tts)")
    parser.add_argument("--material", "-m", required=True, help="通话记录 JSON 路径")
    parser.add_argument("--output", "-o", default="./output", help="音频输出目录")
    args = parser.parse_args()

    try:
        asyncio.run(generate_audio_from_json(args.material, args.output))
    except FileNotFoundError as e:
        print(f"❌ 文件不存在: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"❌ 素材校验失败: {e}", file=sys.stderr)
        return 3
    except Exception as e:  # noqa: BLE001
        print(f"❌ 合成失败: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
