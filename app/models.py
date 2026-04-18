from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class AnalysisResult:
    report_markdown: str
    match_score: int = 0
    match_summary: str = ""
    strengths: List[str] = None
    gaps: List[str] = None
    suggestions: List[str] = None

    def __post_init__(self) -> None:
        self.strengths = self.strengths or []
        self.gaps = self.gaps or []
        self.suggestions = self.suggestions or []


@dataclass
class OptimizationResult:
    optimized_resume_md: str
    change_log: List[str]


@dataclass
class SessionData:
    session_id: str
    created_at: datetime
    original_resume: str
    job_description: str
    analysis: Optional[AnalysisResult] = None
    optimized: Optional[OptimizationResult] = None
    focus_notes: str = ""
    source_filename: str = ""


@dataclass
class ExportPayload:
    filename: str
    content: str
    media_type: str


def normalize_bullets(items: List[str]) -> List[str]:
    cleaned: List[str] = []
    for item in items:
        text = " ".join(str(item).split())
        if text:
            cleaned.append(text)
    return cleaned
