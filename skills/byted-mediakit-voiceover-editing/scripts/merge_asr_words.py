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

"""将 step5_asr_raw 的 words 逐字结构合并到 step5_asr_optimized.json"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from project_paths import get_project_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir", default="", help="输出目录，默认 output；可指定 output/<文件名>"
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
            out_dir = resolved
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
            out_dir = resolved
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = get_project_root() / "output"
    opt_path = out_dir / "step5_asr_optimized.json"
    raw_glob = list(out_dir.glob("step5_asr_raw_*.json"))

    if not opt_path.exists():
        print("error: step5_asr_optimized.json not found")
        sys.exit(1)
    if not raw_glob:
        print("error: no step5_asr_raw_*.json found")
        sys.exit(1)

    opt = json.loads(opt_path.read_text(encoding="utf-8"))
    raw = json.loads(raw_glob[0].read_text(encoding="utf-8"))
    utterances = raw.get("result", {}).get("utterances", [])

    def ms(s: float) -> int:
        return int(round(s * 1000))

    out_segments = []
    ui = 0
    for seg in opt.get("optimized_segments", []):
        start_ms = ms(seg["start_time"])
        end_ms = ms(seg["end_time"])
        opt_text = seg.get("text", "")
        src_text = seg.get("source_text", "")

        # 找时间最匹配的 utterance
        best = None
        for i, u in enumerate(utterances):
            if abs(u["start_time"] - start_ms) < 100:
                best = i
                break
        if best is None:
            best = min(ui, len(utterances) - 1)

        u = utterances[best]
        words = list(u.get("words", []))
        ui = best + 1

        # 同音纠错：opt_text 与 words 拼接结果逐字比对，纠正不同的字
        src_from_words = "".join(w.get("text", "") for w in words)
        if len(opt_text) == len(src_from_words):
            for wi, (pt, sw) in enumerate(zip(opt_text, src_from_words)):
                if wi < len(words) and pt != sw:
                    words[wi] = {**words[wi], "text": pt}

        # 输出 words，与源结构一致；-1 时间戳原样保留
        out_words = [
            {
                "text": w["text"],
                "start_time": w["start_time"],
                "end_time": w["end_time"],
            }
            for w in words
        ]

        out_segments.append(
            {
                "text": seg["text"],
                "source_text": src_text,
                "start_time": seg["start_time"],
                "end_time": seg["end_time"],
                "words": out_words,
            }
        )

    opt["optimized_segments"] = out_segments
    opt_path.write_text(json.dumps(opt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"merged words into {opt_path}")


if __name__ == "__main__":
    main()
