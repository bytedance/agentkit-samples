#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ALLOWED_FIELDS = {
    "email",
    "candidate_name",
    "is_qualified",
    "gender",
    "industry",
    "current_position",
    "years_of_exp",
    "job_switch_intent",
    "candidate_focus",
    "notes",
    "transcript_text",
    "project_experience",
    "technical_capability",
    "education_level",
    "jd_years_match",
    "jd_match_score",
    "screening_stage",
    "screening_decision",
    "screening_reason",
    "strengths_summary",
    "weaknesses_summary",
    "final_match_score",
    "final_recommendation",
    "ai_match_conclusion",
    "ai_match_evidence",
    "last_call_date",
}


def resolve_full_transcript(item: dict) -> str:
    transcript = item.get("transcript")
    if isinstance(transcript, dict):
        text = transcript.get("text")
        if text:
            return str(text).strip()
    text = item.get("transcript_text")
    if text:
        return str(text).strip()
    return ""


def load_crm_module():
    skill_root = Path(__file__).resolve().parents[1]
    crm_main = skill_root.parent / "byted-arkclaw-local-hr-crm" / "scripts" / "main.py"
    if not crm_main.exists():
        raise FileNotFoundError(f"未找到 CRM 脚本: {crm_main}")

    spec = importlib.util.spec_from_file_location("byted_arkclaw_local_hr_crm_main", crm_main)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 CRM 模块")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description="将 assessment.json 写入 CRM")
    parser.add_argument("--profile-json", required=True)
    parser.add_argument("--phone-source", default="")
    args = parser.parse_args()

    payload = json.loads(
        Path(args.profile_json).expanduser().resolve().read_text(encoding="utf-8")
    )
    crm_module = load_crm_module()

    if isinstance(payload, dict) and isinstance(payload.get("crm_payload"), dict):
        payload = payload["crm_payload"]

    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict) and isinstance(payload.get("candidates"), list):
        candidates = payload["candidates"]
    else:
        candidates = [payload]

    outputs = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        phone_source = (
            args.phone_source
            or item.get("phone")
            or item.get("phone_source")
            or item.get("source_file")
            or (item.get("candidate_hint") or {}).get("source_file", "")
            or (item.get("candidate_hint") or {}).get("phone", "")
        )
        if not phone_source:
            raise SystemExit("❌ 缺少候选人手机号，无法写入 CRM")

        fields = {
            key: value for key, value in item.items() if key in ALLOWED_FIELDS and value is not None
        }
        full_transcript = resolve_full_transcript(item)
        if full_transcript:
            # Always persist the full original transcript, not an AI summary.
            fields["transcript_text"] = full_transcript
        outputs.append(crm_module.main("upsert", phone_source, **fields))

    print("\n\n".join(outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
