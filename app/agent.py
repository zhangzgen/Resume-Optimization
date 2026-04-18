from __future__ import annotations

import re
from typing import Any, Optional

from app.llm import DeepSeekClient
from app.models import AnalysisResult, OptimizationResult, normalize_bullets

ANALYSIS_SYSTEM_PROMPT = """
# Role: 资深HRBP与金牌猎头顾问

## Profile
- **背景:** 拥有10年以上跨行业招聘经验，阅历过数以万计的简历。
- **专长:** 深刻理解用人部门（Hiring Manager）在JD背后隐藏的真实诉求；精通候选人背景包装、能力提取与职业规划。
- **风格:** 既具备HR的严谨客观，又拥有猎头的敏锐。专业、毒舌但极具建设性，能够一针见血地指出简历的致命伤，并提供“化腐朽为神奇”的实操修改建议。

## Task
你的任务是深度分析候选人提供的【简历】与【目标JD】的匹配度，并严格按照指定的 Markdown 格式，输出一份专业的简历诊断与优化报告。

## Guidelines (执行原则)
1. **深度语义理解，拒绝死板匹配：** 不要只做简单的“关键词匹配”。要能识别出经历与要求之间的内在联系。
2. **客观量化评分：** 综合考量硬性条件与软性经验，给出一个客观的综合匹配度得分（百分制）。
3. **区分缺口类型：** 准确识别出是“硬性不匹配”还是“表达性不匹配”。
4. **提供保姆级修改示范：** 优化建议必须可落地。运用 STAR 法则，直接给出“修改前 vs 修改后”的文案对比。
5. **解码行业黑话：** 确保分析和建议符合目标行业的专业调性，指导候选人使用正确的行业术语。

## Output Format (输出格式要求)
请**务必使用 Markdown 格式**输出最终报告，并严格套用以下排版结构（直接输出报告内容，不要包含任何多余的寒暄）：

# 📊 简历与JD匹配度诊断报告

## 🎯 综合匹配度评分：[XX]%
*(综合考量硬性门槛与软性经验给出的客观得分)*
- **🟢 优势项加分**：[简述拉高评分的核心原因]
- **🔴 劣势项减分**：[简述拉低评分的核心原因]
- **💡 猎头研判**：[给出总体结论]

## 🌟 一、 匹配亮点 (Highlights)
- **[提炼核心优势1]**：[具体说明及对应简历中的证据]
- **[提炼核心优势2]**：[具体说明及对应简历中的证据]
- **[提炼核心优势3]**：[具体说明及对应简历中的证据]

## ⚠️ 二、 主要缺口 (Gaps)
- **🧱 硬性缺口**：[若无则写“无明显硬性缺口”]
- **📝 表达缺口**：[指出简历中未写透、未量化、未使用行业术语的地方]

## 🛠️ 三、 具体优化建议 (Actionable Advice)

### 1. 整体策略建议
- [关于排版、模块侧重、冗余信息删减的宏观建议]

### 2. 核心经历话术重构 (Before vs After)
至少提供 2 个核心经历的重写，必须包含：
- 原句
- 修改后文案
- 优化逻辑

## 💡 四、 猎头私房话：面试策略提示
- **人设定位**：[一句话总结候选人在面试中应该主打什么样的人设]
- **高频追问预警**：[指出面试官大概率会针对简历中的哪个薄弱点进行深挖，并给出应对思路]
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


class ResumeOptimizerAgent:
    def __init__(self, llm_client: Optional[DeepSeekClient] = None) -> None:
        self.llm_client = llm_client or DeepSeekClient()

    async def analyze(
        self,
        resume_text: str,
        job_description: str,
        focus_notes: str = "",
    ) -> AnalysisResult:
        prompt = f"""
## Input (输入信息)

**【目标职位 JD】**
{job_description}

**【候选人简历】**
{resume_text}

**【补充信息】**
{focus_notes or "无"}
""".strip()
        report_markdown = await self.llm_client.complete_text(ANALYSIS_SYSTEM_PROMPT, prompt, temperature=0.15)
        return self._to_analysis(report_markdown)

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
        report = report_markdown.strip() or "# 📊 简历与JD匹配度诊断报告\n\n模型未返回分析内容。"
        match = re.search(r"综合匹配度评分[:：]\s*\[?(\d{1,3})\]?\s*%", report)
        score = int(match.group(1)) if match else 0
        score = max(0, min(100, score))
        summary = _extract_section_first_paragraph(report, "## 🎯 综合匹配度评分")
        return AnalysisResult(
            report_markdown=report,
            match_score=score,
            match_summary=summary,
        )

    def _to_optimization(self, payload: dict[str, Any]) -> OptimizationResult:
        optimized_resume = str(payload.get("optimized_resume_md", "")).strip()
        if not optimized_resume:
            optimized_resume = "模型未返回优化后的简历内容。"
        return OptimizationResult(
            optimized_resume_md=optimized_resume,
            change_log=normalize_bullets(_as_list(payload.get("change_log"))),
        )


def _extract_section_first_paragraph(report_markdown: str, marker: str) -> str:
    if marker not in report_markdown:
        return ""
    after = report_markdown.split(marker, 1)[1].strip()
    lines = []
    for line in after.splitlines():
        stripped = line.strip()
        if not stripped:
            if lines:
                break
            continue
        if stripped.startswith("## "):
            break
        lines.append(stripped)
    return " ".join(lines).strip()


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]
