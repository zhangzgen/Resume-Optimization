import json
import unittest

from fastapi.testclient import TestClient

import app.main as main
from app.models import AnalysisResult, OptimizationResult


class FakeAgent:
    async def score_only(self, resume_text: str, job_description: str, focus_notes: str = "") -> dict:
        return {"score": 82, "summary": "具备核心技能匹配，经验丰富。"}

    async def stream_score(self, resume_text: str, job_description: str, focus_notes: str = ""):
        yield '{"score": 82, "summary": "具备核心技能匹配，丰富'
        yield '经验。"}'
        yield {"score": 82, "summary": "具备核心技能匹配，经验丰富。"}

    async def analyze(self, resume_text: str, job_description: str, focus_notes: str = "") -> AnalysisResult:
        return AnalysisResult(
            report_markdown="# 📊 详细匹配分析\n\n## 🌟 一、 匹配亮点\n- **FastAPI 经验**：具备实际项目经验\n",
            match_score=0,
        )

    async def stream_analysis(self, resume_text: str, job_description: str, focus_notes: str = ""):
        yield "# 📊 详细匹配分析\n\n"
        yield "## 🌟 一、 匹配亮点\n"
        yield "- **FastAPI 经验**：具备实际项目经验\n"
        yield AnalysisResult(
            report_markdown="# 📊 详细匹配分析\n\n## 🌟 一、 匹配亮点\n- **FastAPI 经验**：具备实际项目经验\n",
            match_score=0,
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

    def test_score_stream_returns_score_json(self) -> None:
        response = self.client.post(
            "/api/analyze-stream",
            data={
                "resume_text": "3 年 Python 与 AI 应用开发经验。",
                "job_description": "需要 FastAPI、LLM 应用开发与跨团队协作。",
                "focus_notes": "突出 AI 项目交付能力",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("score_ready", response.text)
        self.assertIn('"score": 82', response.text)
        # Should NOT contain detail analysis
        self.assertNotIn('"stage": "detail_analysis"', response.text)
        self.assertNotIn("export_ready", response.text)
        # Score phase is non-streaming, so no stage_delta for match_score
        self.assertNotIn('"stage": "match_score", "delta_markdown"', response.text)

    def test_full_flow_score_then_detail(self) -> None:
        # Phase 1: Score
        score_response = self.client.post(
            "/api/analyze-stream",
            data={
                "resume_text": "3 年 Python 与 AI 应用开发经验。",
                "job_description": "需要 FastAPI、LLM 应用开发与跨团队协作。",
                "focus_notes": "",
            },
        )
        self.assertEqual(score_response.status_code, 200)
        self.assertIn("score_ready", score_response.text)

        # Extract session_id
        session_id = None
        for line in score_response.text.split("\n"):
            if line.startswith("data:") and '"session_id"' in line:
                payload = json.loads(line[5:].strip())
                if "session_id" in payload:
                    session_id = payload["session_id"]
                    break
        self.assertIsNotNone(session_id)

        # Phase 2: Detail analysis + optimize
        detail_response = self.client.post(
            "/api/detail-stream",
            data={"session_id": session_id},
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertIn('"stage": "detail_analysis"', detail_response.text)
        self.assertIn("event: export_ready", detail_response.text)

    def test_missing_resume_returns_error(self) -> None:
        response = self.client.post(
            "/api/analyze-stream",
            data={"resume_text": "", "job_description": "需要 FastAPI。"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("event: error", response.text)

    def test_missing_jd_returns_422(self) -> None:
        response = self.client.post(
            "/api/analyze-stream",
            data={"resume_text": "Python 开发经验"},
        )
        self.assertEqual(response.status_code, 422)

    def test_detail_stream_nonexistent_session(self) -> None:
        response = self.client.post(
            "/api/detail-stream",
            data={"session_id": "nonexistent-id"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("event: error", response.text)
        self.assertIn("会话不存在", response.text)


if __name__ == "__main__":
    unittest.main()
