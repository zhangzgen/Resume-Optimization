from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.agent import ResumeOptimizerAgent
from app.config import settings
from app.exporters import build_markdown_export, build_text_export
from app.file_handlers import ResumeFileError, extract_resume_text
from app.llm import LLMConfigError, LLMResponseError
from app.models import AnalysisResult
from app.storage import InMemorySessionStore

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

store = InMemorySessionStore()
agent = ResumeOptimizerAgent()


def render_home(
    request: Request,
    *,
    error: str = "",
    resume_text: str = "",
    job_description: str = "",
    focus_notes: str = "",
    session=None,
):
    response = templates.TemplateResponse(
        request,
        "index.html",
        {
            "settings": settings,
            "error": error,
            "resume_text": resume_text,
            "job_description": job_description,
            "focus_notes": focus_notes,
            "session": session,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _chunk_text(text: str, size: int = 110) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    cursor = 0
    while cursor < len(text):
        end = min(len(text), cursor + size)
        split_at = max(text.rfind("\n", cursor, end), text.rfind(" ", cursor, end))
        if split_at <= cursor + 20:
            split_at = end
        chunks.append(text[cursor:split_at])
        cursor = split_at
    return chunks


def _build_completion_markdown(session_id: str) -> str:
    parts = [
        "### 输出完成",
        "- 优化后的简历已经生成",
        f"- 会话编号：`{session_id[:8]}`",
    ]
    return "\n".join(parts).strip()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return render_home(request)


@app.get("/healthz", response_class=PlainTextResponse)
async def healthz() -> str:
    return "ok"


@app.post("/analyze")
async def analyze_compat() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=303)


@app.post("/optimize")
async def optimize_compat() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=303)


@app.post("/api/analyze-stream")
async def analyze_stream(
    resume_text: str = Form(""),
    job_description: str = Form(...),
    focus_notes: str = Form(""),
    resume_file: Optional[UploadFile] = File(None),
) -> StreamingResponse:
    """Phase 1: Quick match score."""
    try:
        uploaded_resume_text, source_filename = await extract_resume_text(resume_file)
    except ResumeFileError as exc:
        error_msg = str(exc)

        async def failed_upload() -> AsyncIterator[str]:
            yield _sse_event("error", {"message": error_msg})

        return StreamingResponse(failed_upload(), media_type="text/event-stream")

    final_resume_text = (resume_text or "").strip() or uploaded_resume_text
    final_jd = (job_description or "").strip()
    final_focus_notes = (focus_notes or "").strip()

    if not final_resume_text:
        async def missing_resume() -> AsyncIterator[str]:
            yield _sse_event("error", {"message": "请粘贴简历内容或上传简历文件。"})

        return StreamingResponse(missing_resume(), media_type="text/event-stream")
    if not final_jd:
        async def missing_jd() -> AsyncIterator[str]:
            yield _sse_event("error", {"message": "请输入目标职位 JD。"})

        return StreamingResponse(missing_jd(), media_type="text/event-stream")

    session = store.create(final_resume_text, final_jd, source_filename=source_filename)
    session.focus_notes = final_focus_notes
    store.save(session)

    async def event_stream() -> AsyncIterator[str]:
        yield _sse_event(
            "session",
            {
                "session_id": session.session_id,
                "source_filename": source_filename,
                "llm_ready": settings.is_llm_configured,
            },
        )

        # --- Stage 1: Match score (non-streaming) ---
        yield _sse_event("status", {"label": "正在计算匹配度"})
        yield _sse_event("stage_start", {"stage": "match_score", "title": "匹配度评分"})

        try:
            score_json = await agent.score_only(final_resume_text, final_jd, focus_notes=final_focus_notes)
        except (LLMConfigError, LLMResponseError, ValueError) as exc:
            yield _sse_event("error", {"message": str(exc)})
            return
        except Exception as exc:
            yield _sse_event("error", {"message": f"匹配度计算失败：{exc}"})
            return

        yield _sse_event("stage_done", {"stage": "match_score"})
        yield _sse_event("score_ready", {
            "session_id": session.session_id,
            "score": (score_json or {}).get("score", 0),
            "summary": (score_json or {}).get("summary", ""),
        })
        yield _sse_event("status", {"label": "匹配度已出，请点击开始分析"})

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@app.post("/api/detail-stream")
async def detail_stream(
    session_id: str = Form(...),
) -> StreamingResponse:
    """Phase 2: Detailed analysis + optimization, triggered by user click."""
    session = store.get(session_id)
    if session is None:
        async def not_found() -> AsyncIterator[str]:
            yield _sse_event("error", {"message": "会话不存在或已过期，请重新开始。"})

        return StreamingResponse(not_found(), media_type="text/event-stream")

    async def event_stream() -> AsyncIterator[str]:
        # --- Stage 3: Detailed analysis (streaming) ---
        yield _sse_event("status", {"label": "正在生成详细分析"})
        yield _sse_event("detail_start", {})
        yield _sse_event("stage_start", {"stage": "detail_analysis", "title": "详细匹配分析"})

        try:
            analysis_result = None
            async for item in agent.stream_analysis(session.original_resume, session.job_description, focus_notes=session.focus_notes):
                if isinstance(item, AnalysisResult):
                    analysis_result = item
                else:
                    yield _sse_event("stage_delta", {"stage": "detail_analysis", "delta_markdown": item})
            session.analysis = analysis_result
            store.save(session)
        except (LLMConfigError, LLMResponseError, ValueError) as exc:
            yield _sse_event("error", {"message": str(exc)})
            return
        except Exception as exc:
            yield _sse_event("error", {"message": f"分析请求失败：{exc}"})
            return

        yield _sse_event("stage_done", {"stage": "detail_analysis"})

        # --- Stage 4: Optimization ---
        await asyncio.sleep(0.15)
        yield _sse_event("status", {"label": "正在生成优化后的简历"})

        try:
            session.optimized = await agent.optimize(
                session.original_resume,
                session.job_description,
                session.analysis,
                focus_notes=session.focus_notes,
            )
            store.save(session)
        except (LLMConfigError, LLMResponseError, ValueError) as exc:
            yield _sse_event("error", {"message": str(exc)})
            return
        except Exception as exc:
            yield _sse_event("error", {"message": f"优化请求失败：{exc}"})
            return

        yield _sse_event("stage_start", {"stage": "completion", "title": "完成状态"})
        completion_text = _build_completion_markdown(session.session_id)
        for chunk in _chunk_text(completion_text, size=120):
            yield _sse_event("stage_delta", {"stage": "completion", "delta_markdown": chunk})
            await asyncio.sleep(0.015)
        yield _sse_event("stage_done", {"stage": "completion"})
        yield _sse_event(
            "export_ready",
            {
                "session_id": session.session_id,
                "download_url": f"/export/{session.session_id}/md",
            },
        )
        yield _sse_event("status", {"label": "全部完成"})

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@app.get("/export/{session_id}/{fmt}")
async def export_result(session_id: str, fmt: str) -> Response:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在或已过期。")

    if fmt == "md":
        payload = build_markdown_export(session)
    elif fmt == "txt":
        payload = build_text_export(session)
    else:
        raise HTTPException(status_code=400, detail="仅支持导出 md 或 txt。")

    headers = {"Content-Disposition": f'attachment; filename="{payload.filename}"'}
    return Response(content=payload.content, media_type=payload.media_type, headers=headers)


@app.get("/reset")
async def reset() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=303)
