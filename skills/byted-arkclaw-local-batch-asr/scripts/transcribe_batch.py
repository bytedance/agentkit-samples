#!/usr/bin/env python3
"""Local batch transcription runner for byted-arkclaw-local-batch-asr."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from local_batch_asr_runtime import SUPPORTED_FORMATS, SUPPORTED_VIDEO_FORMATS, transcribe

MEDIA_SUFFIXES = set(SUPPORTED_FORMATS) | set(SUPPORTED_VIDEO_FORMATS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch transcribe local audio/video files with FunASR."
    )
    parser.add_argument("input_path", nargs="?", help="Single file or directory to process")
    parser.add_argument("-o", "--output-dir", help="Output run directory")
    parser.add_argument("-f", "--format", choices=["txt", "json", "srt", "ass", "md"], default="txt")
    parser.add_argument("--manifest", help="Text file with one input path per line")
    parser.add_argument("--recursive", action="store_true", help="Recursively scan directories")
    parser.add_argument("--pattern", default="*", help="Filename glob when scanning directories")
    parser.add_argument("--limit", type=int, default=0, help="Stop after N matched files (0 = unlimited)")
    parser.add_argument("--no-diarize", action="store_true", help="Disable speaker diarization attempt")
    parser.add_argument("--continue-on-error", action="store_true", help="Continue even if one file fails")
    return parser.parse_args()


def discover_inputs(args: argparse.Namespace) -> list[Path]:
    if args.manifest:
        manifest_path = Path(args.manifest).expanduser().resolve()
        base_dir = manifest_path.parent
        results = []
        for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            candidate = Path(line)
            if not candidate.is_absolute():
                candidate = (base_dir / candidate).resolve()
            results.append(candidate)
        return results

    if not args.input_path:
        raise ValueError("input_path and --manifest cannot both be empty")

    input_path = Path(args.input_path).expanduser().resolve()
    if input_path.is_file():
        return [input_path]

    if not input_path.is_dir():
        raise FileNotFoundError(f"Input path not found: {input_path}")

    iterator = input_path.rglob(args.pattern) if args.recursive else input_path.glob(args.pattern)
    results = []
    for item in iterator:
        if item.is_file() and item.suffix.lower().lstrip(".") in MEDIA_SUFFIXES:
            results.append(item.resolve())
            if args.limit and len(results) >= args.limit:
                break
    return sorted(results)


def safe_stem(path: Path) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in path.stem) or "file"


def write_summary(run_dir: Path, results: list[dict]) -> None:
    summary = {
        "run_dir": str(run_dir),
        "success_count": sum(1 for item in results if item["status"] == "completed"),
        "failure_count": sum(1 for item in results if item["status"] != "completed"),
        "results": results,
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with (run_dir / "summary.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["source", "status", "format", "output_path", "speaker_count", "segments", "error"],
        )
        writer.writeheader()
        for item in results:
            writer.writerow(
                {
                    "source": item.get("source", ""),
                    "status": item.get("status", ""),
                    "format": item.get("format", ""),
                    "output_path": item.get("output_path", ""),
                    "speaker_count": item.get("speaker_count", 0),
                    "segments": item.get("segments", 0),
                    "error": item.get("error", ""),
                }
            )


def main() -> int:
    args = parse_args()
    inputs = discover_inputs(args)
    if not inputs:
        print(json.dumps({"error": "No supported media files found."}, ensure_ascii=False))
        return 1

    run_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else (SKILL_ROOT / "output" / "run_latest")
    files_dir = run_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    exit_code = 0
    total = len(inputs)

    for index, input_path in enumerate(inputs, start=1):
        print(f"[{index}/{total}] Processing {input_path}")
        file_dir = files_dir / safe_stem(input_path)
        file_dir.mkdir(parents=True, exist_ok=True)

        try:
            result = transcribe(
                input_path,
                output_dir=file_dir,
                format=args.format,
                diarize=not args.no_diarize,
            )
            record = {
                "source": str(input_path),
                "status": "completed",
                "format": args.format,
                "output_path": result["output_path"],
                "speaker_count": len(result.get("speakers", [])),
                "segments": len(result.get("segments", [])),
                "error": None,
            }
        except Exception as exc:
            exit_code = 1
            record = {
                "source": str(input_path),
                "status": "failed",
                "format": args.format,
                "output_path": None,
                "speaker_count": 0,
                "segments": 0,
                "error": str(exc),
            }
            if not args.continue_on_error:
                results.append(record)
                (file_dir / "meta.json").write_text(
                    json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                write_summary(run_dir, results)
                print(json.dumps({"error": str(exc), "source": str(input_path)}, ensure_ascii=False))
                return exit_code

        results.append(record)
        (file_dir / "meta.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    write_summary(run_dir, results)
    print(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "success_count": sum(1 for item in results if item["status"] == "completed"),
                "failure_count": sum(1 for item in results if item["status"] != "completed"),
                "summary_json": str(run_dir / "summary.json"),
                "summary_csv": str(run_dir / "summary.csv"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
