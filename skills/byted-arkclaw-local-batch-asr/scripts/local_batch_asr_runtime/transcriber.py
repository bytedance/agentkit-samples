import json
import re
import subprocess
import tempfile
from collections import OrderedDict
from pathlib import Path
from typing import Any

import imageio_ffmpeg

from .core.device import get_device_with_fallback

SUPPORTED_FORMATS = ("mp3", "wav", "m4a", "flac", "aac", "ogg")
SUPPORTED_VIDEO_FORMATS = ("mp4", "avi", "mkv", "mov")
OUTPUT_FORMATS = ("txt", "json", "srt", "ass", "md")

_MODEL_CACHE: dict[tuple[str, bool], Any] = {}


def _format_seconds(seconds: float, for_srt: bool = False, for_ass: bool = False) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours = total_ms // 3_600_000
    minutes = (total_ms % 3_600_000) // 60_000
    secs = (total_ms % 60_000) // 1000
    ms = total_ms % 1000

    if for_srt:
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"

    if for_ass:
        centiseconds = ms // 10
        return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"

    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def _normalize_time(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (list, tuple)) and value:
        value = value[0]
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return numeric / 1000.0 if numeric > 1000 else numeric


def _speaker_label(raw_value: Any) -> str:
    if raw_value in (None, "", -1):
        return "Speaker A"
    if isinstance(raw_value, str):
        value = raw_value.strip()
        if value.lower().startswith("speaker "):
            return value
        if value.lower().startswith("spk"):
            suffix = value.split("-", 1)[-1].split("_", 1)[-1]
            return f"Speaker {suffix.upper()}"
        return value
    if isinstance(raw_value, (int, float)):
        return f"Speaker {chr(ord('A') + int(raw_value))}"
    return "Speaker A"


def _clean_text(text: str) -> str:
    cleaned = re.sub(r"<\s*\|.*?\|\s*>", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _extract_time_pair(sentence: Any) -> tuple[float, float]:
    if not isinstance(sentence, dict):
        return 0.0, 0.0
    start_raw = sentence.get("start")
    if start_raw is None:
        start_raw = sentence.get("start_time")
    end_raw = sentence.get("end")
    if end_raw is None:
        end_raw = sentence.get("end_time")
    timestamp = sentence.get("timestamp")
    if (start_raw is None or end_raw is None) and isinstance(timestamp, (list, tuple)) and timestamp:
        start_raw = timestamp[0]
        end_raw = timestamp[-1]
    return _normalize_time(start_raw), _normalize_time(end_raw)


def _prepare_wav(input_path: Path, tmp_dir: Path) -> Path:
    output_path = tmp_dir / "prepared.wav"
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_path,
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def _load_model(diarize: bool):
    key = (get_device_with_fallback(), diarize)
    if key in _MODEL_CACHE:
        return _MODEL_CACHE[key]

    from funasr import AutoModel

    kwargs = {
        "model": "iic/SenseVoiceSmall",
        "vad_model": "fsmn-vad",
        "punc_model": "ct-punc",
        "device": key[0],
        "disable_update": True,
    }
    if diarize:
        kwargs["spk_model"] = "cam++"

    model = AutoModel(**kwargs)
    _MODEL_CACHE[key] = model
    return model


def _normalize_segments(raw_result: Any, diarize: bool) -> list[dict[str, Any]]:
    if isinstance(raw_result, list) and raw_result:
        item = raw_result[0]
    elif isinstance(raw_result, dict):
        item = raw_result
    else:
        item = {}

    sentence_info = item.get("sentence_info") or item.get("sentence_infos") or []
    segments: list[dict[str, Any]] = []
    for sentence in sentence_info:
        start, end = _extract_time_pair(sentence)
        text = _clean_text((sentence.get("text") or "").strip())
        speaker = _speaker_label(
            sentence.get("speaker")
            or sentence.get("speaker_id")
            or sentence.get("spk")
            or sentence.get("spkid")
        )
        if text:
            segments.append(
                {
                    "text": text,
                    "start": start,
                    "end": max(end, start),
                    "speaker_id": speaker if diarize else "Speaker A",
                    "confidence": sentence.get("confidence"),
                    "is_overlap": bool(sentence.get("is_overlap", False)),
                    "words": sentence.get("words", []),
                }
            )

    if segments:
        return segments

    text = _clean_text((item.get("text") or "").strip())
    if text:
        return [
            {
                "text": text,
                "start": 0.0,
                "end": 0.0,
                "speaker_id": "Speaker A",
                "confidence": item.get("confidence"),
                "is_overlap": False,
                "words": item.get("words", []),
            }
        ]

    raise RuntimeError("ASR did not return any transcript text.")


def _write_txt(segments: list[dict[str, Any]], output_path: Path) -> None:
    lines = []
    for segment in segments:
        overlap = "[OVERLAP] " if segment["is_overlap"] else ""
        lines.append(f"{overlap}[{_format_seconds(segment['start'])}] {segment['speaker_id']}: {segment['text']}")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_json(segments: list[dict[str, Any]], output_path: Path) -> None:
    payload = []
    for segment in segments:
        payload.append(
            {
                "text": segment["text"],
                "start": int(round(segment["start"] * 1000)),
                "end": int(round(segment["end"] * 1000)),
                "confidence": segment["confidence"],
                "speaker_id": segment["speaker_id"],
                "is_overlap": segment["is_overlap"],
                "words": segment["words"],
            }
        )
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_srt(segments: list[dict[str, Any]], output_path: Path) -> None:
    blocks = []
    for idx, segment in enumerate(segments, start=1):
        end = segment["end"] if segment["end"] > segment["start"] else segment["start"] + 2
        blocks.append(
            "\n".join(
                [
                    str(idx),
                    f"{_format_seconds(segment['start'], for_srt=True)} --> {_format_seconds(end, for_srt=True)}",
                    f"[{segment['speaker_id']}] {segment['text']}",
                ]
            )
        )
    output_path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def _write_ass(segments: list[dict[str, Any]], output_path: Path) -> None:
    speakers = list(OrderedDict((seg["speaker_id"], None) for seg in segments).keys())
    colors = ["&H00FFFF", "&H00FFFF00", "&H00FF00FF", "&H0000FF00", "&H0000A5FF"]
    styles = [
        "Style: Default,Arial,16,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1"
    ]
    style_map = {"Default": "Default"}
    for idx, speaker in enumerate(speakers):
        style_name = speaker.replace(" ", "")
        style_map[speaker] = style_name
        styles.append(
            "Style: "
            f"{style_name},Arial,16,{colors[idx % len(colors)]},&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1"
        )

    dialogues = []
    for segment in segments:
        end = segment["end"] if segment["end"] > segment["start"] else segment["start"] + 2
        text = segment["text"].replace("\\", "\\\\").replace("\n", "\\N")
        dialogues.append(
            "Dialogue: 0,"
            f"{_format_seconds(segment['start'], for_ass=True)},"
            f"{_format_seconds(end, for_ass=True)},"
            f"{style_map[segment['speaker_id']]},,0,0,0,,{text}"
        )

    content = "\n".join(
        [
            "[Script Info]",
            "Title: Transcription",
            "ScriptType: v4.00+",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            *styles,
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
            *dialogues,
            "",
        ]
    )
    output_path.write_text(content, encoding="utf-8")


def _write_md(segments: list[dict[str, Any]], output_path: Path) -> None:
    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for segment in segments:
        grouped.setdefault(segment["speaker_id"], []).append(segment)

    lines = []
    for speaker, items in grouped.items():
        lines.append(f"## {speaker}")
        lines.append("")
        for item in items:
            prefix = "[OVERLAP] " if item["is_overlap"] else ""
            lines.append(f"- [{_format_seconds(item['start'])[:8]}] {prefix}{item['text']}")
        lines.append("")
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_output(segments: list[dict[str, Any]], output_path: Path, format_name: str) -> None:
    writers = {
        "txt": _write_txt,
        "json": _write_json,
        "srt": _write_srt,
        "ass": _write_ass,
        "md": _write_md,
    }
    writers[format_name](segments, output_path)


def _run_generate(model: Any, prepared_audio: Path, with_timestamps: bool) -> Any:
    kwargs = {
        "input": str(prepared_audio),
        "batch_size_s": 60,
        "merge_vad": True,
    }
    if with_timestamps:
        kwargs["sentence_timestamp"] = True
    return model.generate(**kwargs)


def transcribe(
    input_file: str | Path,
    output_dir: str | Path | None = None,
    format: str = "txt",
    diarize: bool = True,
    progress_callback=None,
) -> dict[str, Any]:
    input_path = Path(input_file).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path}")
    if format not in OUTPUT_FORMATS:
        raise ValueError(f"Unsupported output format: {format}")

    suffix = input_path.suffix.lower().lstrip(".")
    if suffix not in SUPPORTED_FORMATS and suffix not in SUPPORTED_VIDEO_FORMATS:
        raise ValueError(f"Unsupported media format: {input_path.suffix}")

    out_dir = Path(output_dir).expanduser().resolve() if output_dir else input_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"transcript.{format}"

    if progress_callback:
        progress_callback(5, 100)

    with tempfile.TemporaryDirectory(prefix="byted-arkclaw-local-batch-asr-") as tmp:
        prepared_audio = _prepare_wav(input_path, Path(tmp))
        if progress_callback:
            progress_callback(20, 100)

        model = _load_model(diarize=diarize)
        try:
            raw_result = _run_generate(model, prepared_audio, with_timestamps=diarize)
        except Exception:
            if not diarize:
                raise
            model = _load_model(diarize=False)
            raw_result = _run_generate(model, prepared_audio, with_timestamps=False)
            diarize = False

    if progress_callback:
        progress_callback(80, 100)

    segments = _normalize_segments(raw_result, diarize=diarize)
    _write_output(segments, output_path, format)

    if progress_callback:
        progress_callback(100, 100)

    speakers = list(OrderedDict((seg["speaker_id"], None) for seg in segments).keys())
    return {
        "text": "\n".join(seg["text"] for seg in segments),
        "output_path": str(output_path),
        "segments": segments,
        "speakers": speakers,
        "diarization_enabled": diarize,
    }
