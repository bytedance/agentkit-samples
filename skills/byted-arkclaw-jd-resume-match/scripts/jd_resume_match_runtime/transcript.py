from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _segments_to_text(payload: Any) -> str:
    if isinstance(payload, list):
        parts = []
        for item in payload:
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]).strip())
        return "\n".join(part for part in parts if part).strip()
    return ""


def load_transcript_payload(transcript_path: str | Path) -> dict[str, Any]:
    path = Path(transcript_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"转写结果不存在: {path}")

    suffix = path.suffix.lower()
    warnings: list[str] = []

    if suffix == ".txt":
        return {
            "path": str(path),
            "format": "txt",
            "source": None,
            "text": _read_text(path),
            "warnings": warnings,
        }

    if suffix == ".json":
        payload = json.loads(_read_text(path) or "{}")
        if isinstance(payload, dict) and payload.get("output_path"):
            nested = load_transcript_payload(payload["output_path"])
            nested["source"] = payload.get("source") or nested.get("source")
            return nested

        if isinstance(payload, dict) and payload.get("results"):
            for item in payload["results"]:
                if item.get("status") == "completed" and item.get("output_path"):
                    nested = load_transcript_payload(item["output_path"])
                    nested["source"] = item.get("source") or nested.get("source")
                    return nested
            warnings.append("summary.json 中未找到成功的 transcript 输出。")

        if isinstance(payload, dict) and payload.get("text"):
            return {
                "path": str(path),
                "format": "json",
                "source": payload.get("source"),
                "text": str(payload["text"]).strip(),
                "warnings": warnings,
            }

        text = _segments_to_text(payload)
        return {
            "path": str(path),
            "format": "json",
            "source": payload.get("source") if isinstance(payload, dict) else None,
            "text": text,
            "warnings": warnings,
        }

    return {
        "path": str(path),
        "format": suffix.lstrip("."),
        "source": None,
        "text": _read_text(path),
        "warnings": warnings,
    }
