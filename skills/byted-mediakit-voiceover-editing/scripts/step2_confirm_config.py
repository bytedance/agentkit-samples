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
import re
import json
import time
from pathlib import Path

from project_paths import get_project_root


def _resolve_output_dir(output_dir: str) -> Path:
    out_str = str(output_dir).strip()
    if not out_str:
        raise SystemExit(
            "ERROR: --output-dir is required (use the same output dir as Step3)"
        )

    proj_root = get_project_root()
    out_base = (proj_root / "output").resolve()

    cand = Path(out_str)
    if cand.is_absolute():
        resolved = cand.resolve()
        try:
            resolved.relative_to(out_base)
        except ValueError:
            raise SystemExit(f"ERROR: --output-dir 必须在 {out_base} 下：{resolved}")
        return resolved

    if not out_str.startswith("output/"):
        raise SystemExit("ERROR: --output-dir 只允许传 `output/<文件名>`（相对路径）")
    resolved = (proj_root / out_str).resolve()
    try:
        resolved.relative_to(out_base)
    except ValueError:
        raise SystemExit(f"ERROR: --output-dir 路径越界：{out_str}")
    return resolved


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _parse_js_array_from_md(md_text: str, const_name: str) -> list[str]:
    """
    从 markdown 中解析形如 `const <name> = ['a', 'b'];` 或多行数组的内容。
    约束：元素使用单引号包裹（本仓库规则文件符合）。
    """
    m = re.search(
        rf"const\s+{re.escape(const_name)}\s*=\s*\[(?P<body>[\s\S]*?)\]\s*;?",
        md_text,
    )
    if not m:
        raise ValueError(f"unable to find const {const_name} array in markdown")
    body = m.group("body")
    items = re.findall(r"'([^']*)'", body)
    return [x.strip() for x in items if str(x).strip()]


def _format_js_array(const_name: str, items: list[str], *, multiline: bool) -> str:
    uniq: list[str] = []
    seen = set()
    for x in items:
        s = str(x).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        uniq.append(s)
    if not multiline:
        inner = ", ".join([f"'{x}'" for x in uniq])
        return f"const {const_name} = [{inner}];"
    lines = [f"const {const_name} = ["]
    for x in uniq:
        lines.append(f"  '{x}',")
    lines.append("]")
    return "\n".join(lines)


def _replace_const_array_in_md(
    md_text: str, const_name: str, new_const_block: str
) -> str:
    pattern = rf"(const\s+{re.escape(const_name)}\s*=\s*\[[\s\S]*?\]\s*;?)"
    if not re.search(pattern, md_text):
        raise ValueError(
            f"unable to replace const {const_name} array in markdown (pattern not found)"
        )
    return re.sub(pattern, new_const_block, md_text, count=1)


def _print_config_snapshot(snapshot: dict) -> None:
    print("\n" + "=" * 60)
    print("Step2 当前配置（已展示给用户）")
    print("=" * 60)
    print(f"- fillerWords（语气词）: {snapshot['fillerWords']}")
    print(f"- endingFillerWords（结尾确认词）: {snapshot['endingFillerWords']}")
    print(f"- stutterPatterns（卡顿词模式）: {snapshot['stutterPatterns']}")
    print("=" * 60 + "\n")


def _apply_updates(
    base: list[str], adds: list[str], removes: list[str]
) -> tuple[list[str], dict]:
    orig = list(base)
    add_list = [a.strip() for a in (adds or []) if str(a).strip()]
    rm_set = {r.strip() for r in (removes or []) if str(r).strip()}

    out: list[str] = []
    seen = set()
    for x in orig:
        if x in rm_set:
            continue
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    for a in add_list:
        if a in rm_set:
            continue
        if a not in seen:
            seen.add(a)
            out.append(a)

    diff = {
        "added": [a for a in add_list if a and a not in orig and a not in rm_set],
        "removed": [r for r in rm_set if r in orig],
    }
    return out, diff


def _append_change_log(
    *, change_log_path: Path, note: str, diffs: dict[str, dict]
) -> None:
    change_log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    if change_log_path.exists():
        base = change_log_path.read_text(encoding="utf-8").rstrip() + "\n"
    else:
        base = "# 变更记录\n\n> Step2 配置更新的追加日志（由脚本生成）。\n\n"

    lines = [base, f"## {ts}\n"]
    if note:
        lines.append(f"- 备注：{note}\n")
    for k in ("fillerWords", "endingFillerWords", "stutterPatterns"):
        d = diffs.get(k) or {}
        added = d.get("added") or []
        removed = d.get("removed") or []
        if not added and not removed:
            continue
        if added:
            lines.append(f"- {k}：新增 {added}\n")
        if removed:
            lines.append(f"- {k}：移除 {removed}\n")
    lines.append("\n")
    change_log_path.write_text("".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step2: 语气词/卡顿词确认与规则更新（确认完成后生成 checkpoint 文件）"
    )
    parser.add_argument(
        "--output-dir", required=True, help="输出目录（必须与后续 Step3 使用同一目录）"
    )
    parser.add_argument(
        "--note", default="", help="可选备注（例如本次确认的规则变更点）"
    )
    parser.add_argument(
        "--add-filler", action="append", default=[], help="新增语气词（可重复传参）"
    )
    parser.add_argument(
        "--remove-filler", action="append", default=[], help="移除语气词（可重复传参）"
    )
    parser.add_argument(
        "--add-ending",
        action="append",
        default=[],
        help="新增结尾确认词/反问词（可重复传参）",
    )
    parser.add_argument(
        "--remove-ending",
        action="append",
        default=[],
        help="移除结尾确认词/反问词（可重复传参）",
    )
    parser.add_argument(
        "--add-stutter",
        action="append",
        default=[],
        help="新增卡顿词模式（可重复传参）",
    )
    parser.add_argument(
        "--remove-stutter",
        action="append",
        default=[],
        help="移除卡顿词模式（可重复传参）",
    )
    args = parser.parse_args()

    out_dir = _resolve_output_dir(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rules_dir = _skill_root() / "references" / "用户规则"
    rule_filler = rules_dir / "2-语气词检测.md"
    rule_stutter = rules_dir / "5-卡顿词.md"
    change_log = rules_dir / "变更记录.md"

    md_filler = rule_filler.read_text(encoding="utf-8")
    md_stutter = rule_stutter.read_text(encoding="utf-8")

    filler_words = _parse_js_array_from_md(md_filler, "fillerWords")
    ending_words = _parse_js_array_from_md(md_filler, "endingFillerWords")
    stutter_patterns = _parse_js_array_from_md(md_stutter, "stutterPatterns")

    snapshot_before = {
        "fillerWords": filler_words,
        "endingFillerWords": ending_words,
        "stutterPatterns": stutter_patterns,
    }
    _print_config_snapshot(snapshot_before)

    diffs: dict[str, dict] = {
        "fillerWords": {"added": [], "removed": []},
        "endingFillerWords": {"added": [], "removed": []},
        "stutterPatterns": {"added": [], "removed": []},
    }

    filler_words2, diffs["fillerWords"] = _apply_updates(
        filler_words, args.add_filler, args.remove_filler
    )
    ending_words2, diffs["endingFillerWords"] = _apply_updates(
        ending_words, args.add_ending, args.remove_ending
    )
    stutter_patterns2, diffs["stutterPatterns"] = _apply_updates(
        stutter_patterns, args.add_stutter, args.remove_stutter
    )
    any_change = any(diffs[k]["added"] or diffs[k]["removed"] for k in diffs)

    if any_change:
        md_filler2 = md_filler
        md_filler2 = _replace_const_array_in_md(
            md_filler2,
            "fillerWords",
            _format_js_array("fillerWords", filler_words2, multiline=False),
        )
        md_filler2 = _replace_const_array_in_md(
            md_filler2,
            "endingFillerWords",
            _format_js_array("endingFillerWords", ending_words2, multiline=False),
        )
        rule_filler.write_text(md_filler2, encoding="utf-8")

        md_stutter2 = md_stutter
        md_stutter2 = _replace_const_array_in_md(
            md_stutter2,
            "stutterPatterns",
            _format_js_array("stutterPatterns", stutter_patterns2, multiline=True),
        )
        rule_stutter.write_text(md_stutter2, encoding="utf-8")

        _append_change_log(
            change_log_path=change_log, note=(args.note or "").strip(), diffs=diffs
        )
        print("✅ 已更新并记录到 变更记录.md")

        snapshot_after = {
            "fillerWords": filler_words2,
            "endingFillerWords": ending_words2,
            "stutterPatterns": stutter_patterns2,
        }
        _print_config_snapshot(snapshot_after)
    else:
        print("✅ 已展示当前配置（无变更）")

    rules_read = [
        "references/用户规则/README.md",
        "references/用户规则/1-核心原则.md",
        "references/用户规则/2-语气词检测.md",
        "references/用户规则/3-静音段处理.md",
        "references/用户规则/4-重复句检测.md",
        "references/用户规则/5-卡顿词.md",
        "references/用户规则/6-句内重复检测.md",
        "references/用户规则/7-连续语气词.md",
        "references/用户规则/8-重说纠正.md",
        "references/用户规则/9-残句检测.md",
        "references/用户规则/10-顺句词删除.md",
    ]
    missing = [p for p in rules_read if not (_skill_root() / p).is_file()]
    if missing:
        print("[警告] 检测到规则文件缺失（仍会生成 checkpoint，但建议先修复文件结构）:")
        for m in missing:
            print(f"  - {m}")

    payload = {
        "step": "step2",
        "confirmed": True,
        "confirmed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rules_read": rules_read,
        "rules_version_note": "read all references/用户规则/*.md",
        "shown_to_user": True,
        "config_snapshot": {
            "fillerWords": filler_words2 if any_change else filler_words,
            "endingFillerWords": ending_words2 if any_change else ending_words,
            "stutterPatterns": stutter_patterns2 if any_change else stutter_patterns,
        },
        "change_diffs": diffs if any_change else {},
        "note": (args.note or "").strip(),
        "_project_root": str(get_project_root()),
        "_rules_dir": str(rules_dir),
    }

    out_path = out_dir / "step2_config_confirmed.json"
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[OK] Step2 checkpoint 已生成: {out_path}")
    print(
        "[OK] 现在可以进入 Step3：运行 pipeline_url_to_asr.py（使用同一 --output-dir）"
    )


if __name__ == "__main__":
    main()
