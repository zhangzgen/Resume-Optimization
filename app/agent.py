from __future__ import annotations

import re
from typing import Any, AsyncIterator, Optional

from app.llm import MiMoClient, extract_json_object
from app.models import AnalysisResult, OptimizationResult, normalize_bullets

SCORE_SYSTEM_PROMPT = """
# Role: 资深HRBP与金牌猎头顾问

你的任务是快速评估候选人简历与目标JD的匹配度，**仅输出 JSON**，不要输出其他内容。

## Output Format (严格输出 JSON)

{
  "score": 85,
  "summary": "一句话概括匹配情况"
}
""".strip()

ANALYSIS_SYSTEM_PROMPT = """
你是一名资深HRBP与猎头顾问，拥有10年以上跨行业招聘经验。请深度分析候选人简历与目标JD，输出一份专业的简历诊断报告。

## 核心原则
1. **深度语义匹配**：识别经历与要求的内在联系，不做简单关键词匹配
2. **区分缺口类型**：区分"硬性不匹配"和"表达性不匹配"
3. **基于真实内容**：所有建议严格基于简历已有内容，禁止编造未提及的数字、项目或成果
4. **专业表达**：使用目标行业的专业术语

## 输出格式（严格遵守，直接输出报告，不要寒暄）

# 📊 详细匹配分析

## 🌟 一、匹配亮点

- **[核心优势1]**：具体说明及简历中的对应证据
- **[核心优势2]**：具体说明及简历中的对应证据
- **[核心优势3]**：具体说明及简历中的对应证据

## ⚠️ 二、主要缺口

- **硬性缺口**：[若无则写"无明显硬性缺口"]
- **表达缺口**：[指出简历中未写透、未量化、未使用行业术语的地方]

## 🛠️ 三、优化建议

### 整体策略
- 关于排版、模块侧重、冗余信息删减的宏观建议

### 表达优化
针对简历中已有真实经历，指出可强化的表达方向，但不要编造未提及的内容。

## 💡 四、面试策略

- **人设定位**：一句话总结候选人面试中应主打的人设
- **高频追问预警**：面试官可能针对简历薄弱点的深挖方向及应对思路

## 📋 五、匹配度总结

| 维度 | 评分 | 说明 |
|------|------|------|
| 技能匹配 | X/10 | 简要说明 |
| 经验匹配 | X/10 | 简要说明 |
| 综合匹配 | X/10 | 简要说明 |
""".strip()

OPTIMIZATION_SYSTEM_PROMPT = """
你是一名资深中英文简历优化专家。
你的任务是基于原始简历、目标 JD 和分析建议，重写一份更适配岗位的简历。

规则：
1. 严禁编造用户没有提供的经历、数字、证书、项目、技能熟练度和工作成果。
2. 可以优化表达、重组结构、强化关键词、突出与 JD 更相关的内容。
3. 如果原始信息不足，不要补造内容；优先保留真实信息并用更有力的方式组织。
4. 输出严格 JSON，字段如下：
{
  "optimized_resume_md": "Markdown 格式的优化后简历全文",
  "change_log": ["本次优化动作1", "本次优化动作2", "本次优化动作3"]
}
5. 简历请使用 Markdown 标题和列表，结构完整、清晰、专业，便于导出。
""".strip()


def _score_prompt(resume_text: str, job_description: str, focus_notes: str = "") -> str:
    return f"""
## Input (输入信息)

**【目标职位 JD】**
{job_description}

**【候选人简历】**
{resume_text}

**【补充信息】**
{focus_notes or "无"}
""".strip()


def _analysis_prompt(resume_text: str, job_description: str, focus_notes: str = "") -> str:
    return f"""
## Input (输入信息)

**【目标职位 JD】**
{job_description}

**【候选人简历】**
{resume_text}

**【补充信息】**
{focus_notes or "无"}
""".strip()


class ResumeOptimizerAgent:
    def __init__(self, llm_client: Optional[MiMoClient] = None) -> None:
        self.llm_client = llm_client or MiMoClient()

    async def score_only(
        self,
        resume_text: str,
        job_description: str,
        focus_notes: str = "",
    ) -> dict[str, Any]:
        """Quick match score, returns JSON."""
        text = await self.llm_client.complete_text(
            SCORE_SYSTEM_PROMPT, _score_prompt(resume_text, job_description, focus_notes), temperature=0,
        )
        return extract_json_object(text)

    async def stream_score(
        self,
        resume_text: str,
        job_description: str,
        focus_notes: str = "",
    ) -> AsyncIterator[str]:
        """Stream score generation. Yields text chunks, final yield is the parsed JSON dict."""
        full_text = ""
        async for chunk in self.llm_client.stream_text(
            SCORE_SYSTEM_PROMPT, _score_prompt(resume_text, job_description, focus_notes), temperature=0,
        ):
            full_text += chunk
            yield chunk
        try:
            yield extract_json_object(full_text)
        except Exception:
            yield {"score": 0, "summary": "匹配度解析失败"}

    async def analyze(
        self,
        resume_text: str,
        job_description: str,
        focus_notes: str = "",
    ) -> AnalysisResult:
        """Detailed analysis without match score."""
        report_markdown = await self.llm_client.complete_text(
            ANALYSIS_SYSTEM_PROMPT, _analysis_prompt(resume_text, job_description, focus_notes), temperature=0.15,
        )
        return self._to_analysis(report_markdown)

    async def stream_analysis(
        self,
        resume_text: str,
        job_description: str,
        focus_notes: str = "",
    ) -> AsyncIterator[Any]:
        """Stream detailed analysis. Yields text chunks, final yield is AnalysisResult."""
        full_text = ""
        async for chunk in self.llm_client.stream_text(
            ANALYSIS_SYSTEM_PROMPT, _analysis_prompt(resume_text, job_description, focus_notes), temperature=0.15,
        ):
            full_text += chunk
            yield chunk
        yield self._to_analysis(full_text)

    async def optimize(
        self,
        resume_text: str,
        job_description: str,
        analysis: AnalysisResult,
        focus_notes: str = "",
    ) -> OptimizationResult:
        prompt = f"""
请根据以下输入生成优化后的简历。

【原始简历】
{resume_text}

【目标 JD】
{job_description}

【诊断报告】
{analysis.report_markdown}

【用户补充关注点】
{focus_notes or "无"}
""".strip()
        payload = await self.llm_client.complete_json(OPTIMIZATION_SYSTEM_PROMPT, prompt, temperature=0.2)
        return self._to_optimization(payload)

    def _to_analysis(self, report_markdown: str) -> AnalysisResult:
        report = report_markdown.strip() or "# 📊 详细匹配分析\n\n模型未返回分析内容。"
        return AnalysisResult(
            report_markdown=report,
            match_score=0,
            match_summary="",
        )

    def _to_optimization(self, payload: dict[str, Any]) -> OptimizationResult:
        optimized_resume = str(payload.get("optimized_resume_md", "")).strip()
        if not optimized_resume:
            optimized_resume = "模型未返回优化后的简历内容。"
        return OptimizationResult(
            optimized_resume_md=optimized_resume,
            change_log=normalize_bullets(_as_list(payload.get("change_log"))),
        )


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]
