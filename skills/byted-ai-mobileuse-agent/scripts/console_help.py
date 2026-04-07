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

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _find_section(lines: list[str], header_prefix: str) -> Optional[Tuple[int, int]]:
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().startswith(header_prefix):
            start = i
            break
    if start is None:
        return None

    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].strip().startswith("### 流程 ") or lines[j].strip().startswith("## "):
            end = j
            break
    return start, end


def _pick_topic(question: str) -> str:
    q = (question or "").lower()

    if any(k in q for k in ["首次使用授权", "授权", "serviceroleforipaas", "paasservicerole", "角色权限"]):
        return "### 流程 2:"
    if any(k in q for k in ["创建业务", "业务创建", "product_id", "业务id"]):
        return "### 流程 4:"
    if any(k in q for k in ["订购", "资源订购", "实例", "pod_id", "就绪", "体验 mobile use agent"]):
        return "### 流程 5:"
    if any(k in q for k in ["操作应用指南", "指南", "上传", "升级", "包名"]):
        return "### 流程 6:"
    if any(k in q for k in ["技能配置", "技能存储位置", "tos://", "对象存储桶", "bucket", "skill"]):
        return "### 流程 7: 配置技能"
    if any(k in q for k in ["上架应用", "应用管理", "apk", "新增应用"]):
        return "### 流程 7： 上架应用"

    if any(k in q for k in ["约束", "规则", "全局", "必须"]):
        return "## 2."
    return "## 1."


def _match_section(lines: list[str], topic: str) -> Optional[Tuple[int, int]]:
    if topic.startswith("### 流程 7: 配置技能"):
        for i, ln in enumerate(lines):
            if ln.strip().startswith("### 流程 7: 配置技能"):
                start = i
                end = len(lines)
                for j in range(i + 1, len(lines)):
                    if lines[j].strip().startswith("### 流程 "):
                        end = j
                        break
                return start, end
        return None

    if topic.startswith("### 流程 7： 上架应用"):
        for i, ln in enumerate(lines):
            if ln.strip().startswith("### 流程 7： 上架应用"):
                start = i
                end = len(lines)
                for j in range(i + 1, len(lines)):
                    if lines[j].strip().startswith("## "):
                        end = j
                        break
                return start, end
        return None

    if topic.startswith("### 流程 "):
        for i, ln in enumerate(lines):
            if ln.strip().startswith(topic):
                start = i
                end = len(lines)
                for j in range(i + 1, len(lines)):
                    if lines[j].strip().startswith("### 流程 ") or lines[j].strip().startswith("## "):
                        end = j
                        break
                return start, end
        return None

    return _find_section(lines, topic)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--question", required=True)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    base = Path(__file__).resolve().parent.parent
    doc_path = base / "references" / "MUA_Agent_Instructions.md"

    try:
        text = _read_text(doc_path)
        lines = text.splitlines()
        topic = _pick_topic(args.question)
        span = _match_section(lines, topic)
        if span is None:
            result: Dict[str, Any] = {
                "ok": True,
                "matched": False,
                "topic": topic,
                "content": "",
                "source": str(doc_path),
            }
        else:
            s, e = span
            excerpt = "\n".join(lines[s:e]).strip() + "\n"
            result = {
                "ok": True,
                "matched": True,
                "topic": topic,
                "content": excerpt,
                "source": str(doc_path),
            }

        if args.pretty:
            print(json.dumps(result, ensure_ascii=False, indent=2) + "\n", end="")
        else:
            print(json.dumps(result, ensure_ascii=False) + "\n", end="")
        return 0
    except Exception as e:
        err = {"ok": False, "error": {"type": type(e).__name__, "message": str(e)}}
        print(json.dumps(err, ensure_ascii=False, indent=2) + "\n", end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
