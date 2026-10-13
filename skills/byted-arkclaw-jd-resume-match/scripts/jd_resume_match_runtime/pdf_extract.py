from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pypdf import PdfReader


def _direct_extract(pdf_path: Path) -> tuple[str, list[dict[str, Any]]]:
    reader = PdfReader(str(pdf_path))
    pages = []
    texts = []
    for idx, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        pages.append({"page": idx, "text_length": len(text)})
        if text:
            texts.append(text)
    return "\n\n".join(texts).strip(), pages


def _ocr_extract(pdf_path: Path) -> tuple[str, list[str]]:
    if not shutil.which("tesseract"):
        return "", ["未检测到 tesseract，无法执行 OCR 回退。"]

    try:
        import fitz
    except Exception:
        return "", ["未安装 PyMuPDF，无法执行 OCR 回退。"]

    warnings = []
    texts = []
    with tempfile.TemporaryDirectory(prefix="jd-resume-ocr-") as tmp:
        doc = fitz.open(str(pdf_path))
        for index, page in enumerate(doc, start=1):
            image_path = Path(tmp) / f"page_{index}.png"
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            pix.save(str(image_path))
            try:
                result = subprocess.run(
                    ["tesseract", str(image_path), "stdout"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                texts.append(result.stdout.strip())
            except subprocess.CalledProcessError as exc:
                warnings.append(f"第 {index} 页 OCR 失败: {exc.stderr.strip() or exc}")
    return "\n\n".join(t for t in texts if t).strip(), warnings


def extract_pdf_text(pdf_path: str | Path) -> dict[str, Any]:
    path = Path(pdf_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"PDF 不存在: {path}")

    direct_text, pages = _direct_extract(path)
    warnings: list[str] = []
    method = "direct"
    text = direct_text

    if len(direct_text) < 120:
        ocr_text, ocr_warnings = _ocr_extract(path)
        warnings.extend(ocr_warnings)
        if len(ocr_text) > len(direct_text):
            text = ocr_text
            method = "ocr"

    if not text:
        warnings.append("未能从 PDF 中提取到有效文本。")

    return {
        "path": str(path),
        "file_name": path.name,
        "method": method,
        "page_count": len(pages),
        "text_length": len(text),
        "warnings": warnings,
        "text": text,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="提取 PDF 文本，必要时回退 OCR")
    parser.add_argument("pdf_path")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()

    payload = extract_pdf_text(args.pdf_path)
    if args.output:
        Path(args.output).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
