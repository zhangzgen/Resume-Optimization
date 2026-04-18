import unittest

from app.exporters import build_markdown_export, build_text_export
from app.models import AnalysisResult, OptimizationResult, SessionData


class ExporterTests(unittest.TestCase):
    def test_markdown_and_text_exports_include_sections(self) -> None:
        session = SessionData(
            session_id="demo",
            created_at=None,
            original_resume="Alice - Python Developer",
            job_description="Need FastAPI and AI integration",
            analysis=AnalysisResult(
                report_markdown="# 📊 简历与JD匹配度诊断报告\n\n## 🎯 综合匹配度评分：[85]%",
                match_score=85,
            ),
            optimized=OptimizationResult(
                optimized_resume_md="# Alice\n- FastAPI\n- AI integration",
                change_log=["重排技能模块"],
            ),
        )

        md_payload = build_markdown_export(session)
        txt_payload = build_text_export(session)

        self.assertIn("## 匹配分析", md_payload.content)
        self.assertIn("## 优化后的简历", md_payload.content)
        self.assertIn("优化后的简历", txt_payload.content)


if __name__ == "__main__":
    unittest.main()
