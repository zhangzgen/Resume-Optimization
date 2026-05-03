# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Resume optimization web app. Users paste/upload a resume + job description, the app first streams a diagnostic report (match score, strengths, gaps) via SSE, then after user confirmation, generates an optimized resume for download. Uses Xiaomi MiMo model (MiMo-V2.5-Pro) via OpenAI-compatible API.

## Commands

```bash
# Local dev
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Tests (unittest, no pytest)
python3 -m unittest discover -s tests

# Docker
docker compose up --build
```

## Environment

Copy `.env.example` to `.env` and set `XIAOMI_API_KEY`. All config is via env vars in `app/config.py` (frozen dataclass `Settings`): `XIAOMI_API_KEY`, `XIAOMI_BASE_URL`, `XIAOMI_MODEL`, `LLM_TIMEOUT`, `APP_HOST`, `APP_PORT`.

## Architecture

Monolith FastAPI app, no separate frontend build. Jinja2 serves `index.html`, vanilla JS in `app/static/app.js` handles SSE streaming and rendering.

**Two-phase request flow:**
1. Frontend POSTs `multipart/form-data` to `/api/analyze-stream`
2. `main.py` creates in-memory session, yields SSE events via `StreamingResponse`
3. `ResumeOptimizerAgent` (`agent.py`) calls `MiMoClient` (`llm.py`) for analysis phase
4. Frontend renders diagnostic report incrementally via custom Markdown parser
5. **User confirms** via "确认并生成优化简历" button
6. Frontend POSTs `session_id` to `/api/optimize-stream`
7. Agent calls LLM for optimization phase, generates resume
8. Right panel enables Markdown download

**Key modules:**
- `app/main.py` — routes + SSE streaming logic. Two endpoints: `/api/analyze-stream` (phase 1), `/api/optimize-stream` (phase 2). Helper functions `_sse_event()`, `_chunk_text()` handle stream formatting
- `app/agent.py` — LLM prompt orchestration. System prompts are Chinese-language strings defined as module constants. Analysis prompt prohibits fabricated examples
- `app/llm.py` — Xiaomi MiMo API client (OpenAI-compatible). `complete_text()` for free-form, `complete_json()` for JSON mode. `extract_json_object()` handles markdown-wrapped JSON from LLM
- `app/storage.py` — `InMemorySessionStore` (thread-safe dict, no DB)
- `app/file_handlers.py` — TXT/MD/PDF upload parsing via pypdf
- `app/exporters.py` — builds MD and TXT export documents from session data

**SSE event types:** `session`, `status`, `stage_start`, `stage_delta`, `stage_done`, `analysis_ready`, `export_ready`, `error`

## Testing

Tests use `unittest.TestCase` + FastAPI `TestClient`. Route tests mock `main.agent` with a `FakeAgent` that returns hardcoded results (score=82). No `conftest.py` or pytest. Run single test: `python3 -m unittest tests.test_exporters`
