#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from jd_resume_match_runtime import extract_pdf_text, load_transcript_payload

PHONE_NAME_FILE_PATTERN = re.compile(
    r"^(1[3-9]\d{9})(?:-([^/\\]+?))?(?:\.[^.]+)?$",
    re.IGNORECASE,
)
PHONE_IN_TEXT_PATTERN = re.compile(r"(?<!\d)(1[3-9]\d{2})[\s-]?(\d{4})[\s-]?(\d{4})(?!\d)")
EMAIL_IN_TEXT_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def parse_phone_source(value: str) -> dict[str, str]:
    raw = (value or "").strip()
    if not raw:
        return {"phone": "", "candidate_name": ""}
    name = Path(raw).name
    match = PHONE_NAME_FILE_PATTERN.fullmatch(name)
    if not match:
        return {"phone": "", "candidate_name": ""}
    return {
        "phone": match.group(1) or "",
        "candidate_name": (match.group(2) or "").strip(),
    }


def parse_phone_from_resume_text(text: str) -> str:
    match = PHONE_IN_TEXT_PATTERN.search(text or "")
    if not match:
        return ""
    return "".join(match.groups())


def parse_email_from_resume_text(text: str) -> str:
    match = EMAIL_IN_TEXT_PATTERN.search(text or "")
    if not match:
        return ""
    return match.group(0)


def resolve_candidate_identity(
    resume_payload: dict,
    transcript_payload: dict,
    phone_source: str,
) -> tuple[str, dict[str, str]]:
    resume_phone = parse_phone_from_resume_text(resume_payload.get("text", ""))
    if resume_phone:
        fallback_name = parse_phone_source(phone_source).get("candidate_name", "")
        if not fallback_name:
            fallback_name = parse_phone_source(transcript_payload.get("source") or "").get(
                "candidate_name", ""
            )
        if not fallback_name:
            fallback_name = parse_phone_source(resume_payload.get("path", "")).get(
                "candidate_name", ""
            )
        return resume_payload.get("path", ""), {
            "phone": resume_phone,
            "candidate_name": fallback_name,
        }

    identity_sources = [
        phone_source,
        transcript_payload.get("source") or "",
        resume_payload.get("path", ""),
    ]
    for source in identity_sources:
        hint = parse_phone_source(source)
        if hint.get("phone"):
            return source, hint
    raise ValueError(
        f"候选人简历中缺少可解析的手机号：{resume_payload.get('path', '')}。"
        "初筛建档必须从简历文本抽取结果中识别手机号，若抽取失败请检查简历 PDF 文本质量。"
    )


def load_manifest(path: str | Path) -> list[str]:
    manifest = Path(path).expanduser().resolve()
    base_dir = manifest.parent
    results = []
    for raw_line in manifest.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        item = Path(line)
        if not item.is_absolute():
            item = (base_dir / item).resolve()
        results.append(str(item))
    return results


def discover_resumes(args: argparse.Namespace) -> list[str]:
    resumes: list[str] = []
    for item in args.resume_pdf or []:
        resumes.append(str(Path(item).expanduser().resolve()))

    if args.resume_manifest:
        resumes.extend(load_manifest(args.resume_manifest))

    if args.resume_dir:
        resume_dir = Path(args.resume_dir).expanduser().resolve()
        for file in sorted(resume_dir.glob("*.pdf")):
            resumes.append(str(file.resolve()))

    deduped = []
    seen = set()
    for item in resumes:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def normalize_optional_list(values: list[str] | None, total: int) -> list[str]:
    items = list(values or [])
    if not items:
        return [""] * total
    if len(items) == 1 and total > 1:
        return items * total
    if len(items) != total:
        raise ValueError(f"可选参数数量不匹配，期望 1 或 {total}，实际为 {len(items)}")
    return items


def build_candidate_entry(
    resume_pdf: str,
    transcript_path: str,
    phone_source: str,
    screening_stage: str,
) -> dict:
    resume_payload = extract_pdf_text(resume_pdf)
    transcript_payload = (
        load_transcript_payload(transcript_path) if transcript_path else {"path": "", "format": "", "source": None, "text": "", "warnings": []}
    )
    source_file, candidate_hint = resolve_candidate_identity(
        resume_payload=resume_payload,
        transcript_payload=transcript_payload,
        phone_source=phone_source,
    )

    return {
        "phone": candidate_hint["phone"],
        "email": parse_email_from_resume_text(resume_payload.get("text", "")),
        "resume": resume_payload,
        "transcript": transcript_payload,
        "candidate_hint": {
            "source_file": source_file,
            **candidate_hint,
        },
        "screening_stage": screening_stage,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="整理 1 个 JD 与多位候选人的简历/转写结果为统一分析包")
    parser.add_argument("--jd-pdf", required=True)
    parser.add_argument("--resume-pdf", action="append", help="候选人简历 PDF，可重复传入多次")
    parser.add_argument("--resume-dir", help="批量简历目录，扫描其中的 PDF")
    parser.add_argument("--resume-manifest", help="简历清单文件，每行一个 PDF 路径")
    parser.add_argument("--transcript", action="append", help="候选人对应的转写结果，可不传")
    parser.add_argument("--phone-source", action="append", help="候选人电话或原始录音标识，可不传")
    parser.add_argument("--screening-stage", default="resume_screened", help="本次分析阶段标记")
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args()

    resumes = discover_resumes(args)
    if not resumes:
        raise SystemExit("❌ 至少需要提供一个候选人简历：--resume-pdf / --resume-dir / --resume-manifest")

    transcripts = normalize_optional_list(args.transcript, len(resumes))
    phone_sources = normalize_optional_list(args.phone_source, len(resumes))

    jd_payload = extract_pdf_text(args.jd_pdf)
    candidates = []
    for resume_pdf, transcript_path, phone_source in zip(resumes, transcripts, phone_sources):
        candidates.append(
            build_candidate_entry(
                resume_pdf=resume_pdf,
                transcript_path=transcript_path,
                phone_source=phone_source,
                screening_stage=args.screening_stage,
            )
        )

    bundle = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "batch_candidates",
        "jd": jd_payload,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "required_crm_fields": [
            "phone",
            "email",
            "candidate_name",
            "screening_stage",
            "screening_decision",
            "screening_reason",
            "strengths_summary",
            "weaknesses_summary",
            "transcript_text",
            "project_experience",
            "technical_capability",
            "education_level",
            "years_of_exp",
            "jd_years_match",
            "jd_match_score",
            "final_match_score",
            "final_recommendation",
            "ai_match_conclusion",
            "ai_match_evidence",
        ],
    }

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output_path),
                "jd_text_length": jd_payload["text_length"],
                "candidate_count": len(candidates),
                "candidates": [
                    {
                        "resume": item["resume"]["file_name"],
                        "candidate_hint": item["candidate_hint"],
                        "transcript_length": len(item["transcript"].get("text", "")),
                    }
                    for item in candidates
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
