#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根据用户提示生成通话记录 JSON 骨架。

两种使用方式：

1. 命令行直连（推荐给 Agent 使用）:

   python scripts/generate_record.py \
       --name "FDE 面试邀约" \
       --scenario interview_invite \
       --outcome accept \
       --caller "猎头（张）:zh-CN-XiaoxiaoNeural" \
       --callee "候选人（陈）:zh-CN-YunxiNeural" \
       --duration "约1分钟" \
       --output-file 13111111111-陈先生.mp3 \
       --turns 10 \
       --out materials/fde_interview_accept.json

   脚本会产出带占位台词（`<TODO: ...>`）的 JSON 骨架，Agent 负责再写入实际台词。

2. 交互式:

   python scripts/generate_record.py --interactive --out materials/my.json
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path


VALID_OUTCOMES = {"accept", "reject", "pending", "complaint", "followup", "other"}
PHONE_PREFIXES = ("13", "15", "17", "18", "19")
FEMALE_VOICE_HINTS = ("Xiaoxiao", "Xiaoyi", "Xiaochen", "Xiaohan", "Xiaomeng")
MALE_VOICE_HINTS = ("Yunxi", "Yunyang", "Yunjian", "Yunhao", "Yunze")


def _parse_role_voice(raw: str, role_name: str) -> dict:
    """解析 "角色名:voice" 字符串。"""
    if ":" not in raw:
        raise ValueError(
            f"--{role_name} 需要形如 '角色名:zh-CN-XiaoxiaoNeural' 的格式，收到: {raw}"
        )
    role, voice = raw.split(":", 1)
    role = role.strip()
    voice = voice.strip()
    if not role or not voice:
        raise ValueError(f"--{role_name} 角色名与 voice 均不能为空: {raw}")
    return {"role": role, "voice": voice}


def _generate_virtual_phone_filename() -> str:
    """生成 11 位虚拟手机号。"""
    prefix = random.choice(PHONE_PREFIXES)
    suffix = "".join(random.choices("0123456789", k=9))
    return f"{prefix}{suffix}"


def _infer_gender(callee_role: str, callee_voice: str) -> str:
    """根据角色名和 voice 推断性别，返回 female/male/unknown。"""
    role = callee_role.strip()
    if re.search(r"(女士|小姐|女生|女性|女)", role):
        return "female"
    if re.search(r"(先生|男生|男性|男)", role):
        return "male"

    for hint in FEMALE_VOICE_HINTS:
        if hint in callee_voice:
            return "female"
    for hint in MALE_VOICE_HINTS:
        if hint in callee_voice:
            return "male"
    return "unknown"


def _extract_callee_name(callee_role: str, callee_voice: str) -> str:
    """从被叫角色中提取用于文件名的姓名标签。"""
    role = callee_role.strip()
    gender = _infer_gender(callee_role, callee_voice)
    match = re.search(r"[（(]([^）)]+)[）)]", role)
    if match:
        label = re.sub(r"\s+", "", match.group(1))
    else:
        # 没有括号时，尽量去掉常见身份前缀，保留剩余姓名部分
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


def _normalize_output_file(output_file: str | None, callee_role: str, callee_voice: str) -> str:
    """将输出文件名规范为 `手机号-被叫人姓名.mp3`。"""
    callee_name = _extract_callee_name(callee_role, callee_voice)
    if output_file:
        file_name = Path(output_file).name
        if re.fullmatch(rf"1\d{{10}}-{re.escape(callee_name)}\.mp3", file_name):
            return file_name
    return f"{_generate_virtual_phone_filename()}-{callee_name}.mp3"


def build_skeleton(
    name: str,
    scenario: str,
    outcome: str,
    caller: dict,
    callee: dict,
    duration: str,
    output_file: str,
    turns: int,
    candidate_email: str = "",
) -> dict:
    """构造通话记录骨架，caller/callee 交替发言。"""
    if turns < 2:
        raise ValueError("turns 至少为 2")
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"outcome 必须属于 {sorted(VALID_OUTCOMES)}，收到: {outcome}")

    conversations = []
    for i in range(turns):
        speaker = caller if i % 2 == 0 else callee
        conversations.append(
            {
                "role": speaker["role"],
                "text": f"<TODO: 第{i + 1}轮 {speaker['role']} 的台词>",
                "voice": speaker["voice"],
            }
        )

    material = {
        "name": name,
        "duration": duration,
        "output_file": _normalize_output_file(
            output_file, callee["role"], callee["voice"]
        ),
        "scenario": scenario,
        "outcome": outcome,
        "conversations": conversations,
    }
    if candidate_email:
        material["candidate_email"] = candidate_email.strip()
    return material


def _interactive() -> dict:
    print("== 进入交互式生成模式 ==")
    name = input("对话名称: ").strip()
    scenario = input("场景标签 (如 interview_invite / collection / aftersales): ").strip() or "general"
    outcome = input(f"预期结果 {sorted(VALID_OUTCOMES)}: ").strip() or "other"
    caller_raw = input("主叫 '角色名:voice' (如 猎头（张）:zh-CN-XiaoxiaoNeural): ").strip()
    callee_raw = input("被叫 '角色名:voice' (如 候选人（陈）:zh-CN-YunxiNeural): ").strip()
    duration = input("预计时长 (默认 约1分钟): ").strip() or "约1分钟"
    output_file = input("输出文件名（默认自动生成，如 13111111111-陈.mp3）: ").strip()
    candidate_email = input("候选人邮箱（可选，用于后续邮件邀约）: ").strip()
    turns_raw = input("对话轮次 (默认 10): ").strip() or "10"

    return build_skeleton(
        name=name,
        scenario=scenario,
        outcome=outcome,
        caller=_parse_role_voice(caller_raw, "caller"),
        callee=_parse_role_voice(callee_raw, "callee"),
        duration=duration,
        output_file=output_file,
        turns=int(turns_raw),
        candidate_email=candidate_email,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="通话记录 JSON 骨架生成器")
    parser.add_argument("--interactive", action="store_true", help="进入交互式输入")
    parser.add_argument("--name", help="对话名称")
    parser.add_argument("--scenario", default="general", help="场景标签")
    parser.add_argument(
        "--outcome",
        default="other",
        choices=sorted(VALID_OUTCOMES),
        help="预期结果",
    )
    parser.add_argument("--caller", help="主叫 '角色名:voice'")
    parser.add_argument("--callee", help="被叫 '角色名:voice'")
    parser.add_argument("--duration", default="约1分钟", help="预计时长")
    parser.add_argument("--output-file", help="输出 mp3 文件名")
    parser.add_argument("--candidate-email", default="", help="候选人邮箱（可选，用于后续邮件邀约）")
    parser.add_argument("--turns", type=int, default=10, help="对话轮次（偶数更均衡）")
    parser.add_argument("--out", required=True, help="输出 JSON 路径")
    args = parser.parse_args()

    try:
        if args.interactive:
            material = _interactive()
        else:
            missing = [k for k in ("name", "caller", "callee") if not getattr(args, k.replace("-", "_"), None)]
            if missing:
                parser.error(f"非交互式模式下必须提供: --{', --'.join(missing)}")
            material = build_skeleton(
                name=args.name,
                scenario=args.scenario,
                outcome=args.outcome,
                caller=_parse_role_voice(args.caller, "caller"),
                callee=_parse_role_voice(args.callee, "callee"),
                duration=args.duration,
                output_file=args.output_file,
                turns=args.turns,
                candidate_email=args.candidate_email,
            )
    except ValueError as e:
        print(f"❌ 参数错误: {e}", file=sys.stderr)
        return 2

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(material, f, ensure_ascii=False, indent=2)
    print(f"✅ 通话记录骨架已写入: {out_path}")
    print(f"📞 输出音频文件名: {material['output_file']}")
    print("👉 下一步: 手动/Agent 填充 conversations[*].text 中的 <TODO: ...> 占位台词")
    return 0


if __name__ == "__main__":
    sys.exit(main())
