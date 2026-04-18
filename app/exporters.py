from __future__ import annotations

from app.models import ExportPayload, SessionData


def build_markdown_export(session: SessionData) -> ExportPayload:
    content = [
        "# 简历优化结果",
        "",
        "## 原始信息",
        "",
        "### 原始简历",
        session.original_resume.strip(),
        "",
        "### 目标 JD",
        session.job_description.strip(),
        "",
    ]

    if session.analysis:
        analysis = session.analysis
        content.extend(
            [
                "## 匹配分析",
                "",
                analysis.report_markdown.strip(),
                "",
            ]
        )

    if session.optimized:
        content.extend(
            [
                "## 优化后的简历",
                "",
                session.optimized.optimized_resume_md.strip(),
                "",
                "## 本次优化动作",
                *[f"- {item}" for item in session.optimized.change_log],
                "",
            ]
        )

    return ExportPayload(
        filename=f"resume-optimizer-{session.session_id}.md",
        content="\n".join(content).strip() + "\n",
        media_type="text/markdown; charset=utf-8",
    )


def build_text_export(session: SessionData) -> ExportPayload:
    md = build_markdown_export(session).content
    text = md.replace("# ", "").replace("## ", "").replace("### ", "")
    return ExportPayload(
        filename=f"resume-optimizer-{session.session_id}.txt",
        content=text,
        media_type="text/plain; charset=utf-8",
    )
