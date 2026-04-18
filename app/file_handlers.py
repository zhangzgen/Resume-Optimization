from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

from fastapi import UploadFile


class ResumeFileError(ValueError):
    """Raised when uploaded resume files cannot be parsed."""


SUPPORTED_SUFFIXES = {".txt", ".md", ".pdf"}


async def extract_resume_text(upload: Optional[UploadFile]) -> Tuple[str, str]:
    if upload is None or not upload.filename:
        return "", ""

    suffix = Path(upload.filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ResumeFileError("仅支持上传 TXT、MD 或 PDF 文件。")

    raw = await upload.read()
    if not raw:
        raise ResumeFileError("上传文件为空，请重新选择文件。")

    if suffix in {".txt", ".md"}:
        return raw.decode("utf-8", errors="ignore").strip(), upload.filename

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ResumeFileError("当前环境缺少 PDF 解析依赖，请安装 pypdf。") from exc

    reader = PdfReader(BytesIO(raw))
    pages = []
    for page in reader.pages:
        pages.append((page.extract_text() or "").strip())
    text = "\n\n".join(filter(None, pages)).strip()
    if not text:
        raise ResumeFileError("PDF 中未提取到可用文本，请尝试复制简历文本直接粘贴。")
    return text, upload.filename
