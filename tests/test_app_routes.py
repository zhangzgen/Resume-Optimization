import unittest

from fastapi.testclient import TestClient

import app.main as main
from app.models import AnalysisResult, OptimizationResult


class FakeAgent:
    async def analyze(self, resume_text: str, job_description: str, focus_notes: str = "") -> AnalysisResult:
        return AnalysisResult(
            report_markdown=(
                "# 📊 简历与JD匹配度诊断报告\n\n"
                "## 🎯 综合匹配度评分：[82]%\n"
                "- **🟢 优势项加分**：具备 FastAPI 与 LLM 集成经验\n"
                "- **🔴 劣势项减分**：缺少更明确的业务结果表达\n"
            ),
            match_score=82,
        )

    async def optimize(
        self,
        resume_text: str,
        job_description: str,
        analysis: AnalysisResult,
        focus_notes: str = "",
    ) -> OptimizationResult:
        return OptimizationResult(
            optimized_resume_md="# 优化后简历\n- 强调 AI 应用交付\n- 强调 FastAPI 经验",
            change_log=["重排项目顺序"],
        )


class AppRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_agent = main.agent
        main.agent = FakeAgent()
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        main.agent = self.original_agent
        self.client.close()

    def test_compat_routes_redirect_instead_of_404(self) -> None:
        analyze_response = self.client.post("/analyze", follow_redirects=False)
        optimize_response = self.client.post("/optimize", follow_redirects=False)

        self.assertEqual(analyze_response.status_code, 303)
        self.assertEqual(optimize_response.status_code, 303)
        self.assertEqual(analyze_response.headers["location"], "/")
        self.assertEqual(optimize_response.headers["location"], "/")

    def test_streaming_endpoint_emits_stage_events_and_export_ready(self) -> None:
        response = self.client.post(
            "/api/optimize-stream",
            data={
                "resume_text": "3 年 Python 与 AI 应用开发经验。",
                "job_description": "需要 FastAPI、LLM 应用开发与跨团队协作。",
                "focus_notes": "突出 AI 项目交付能力",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: stage_start", response.text)
        self.assertIn('"stage": "input_summary"', response.text)
        self.assertIn('"stage": "match_analysis"', response.text)
        self.assertIn('"stage": "completion"', response.text)
        self.assertIn("event: export_ready", response.text)


if __name__ == "__main__":
    unittest.main()
