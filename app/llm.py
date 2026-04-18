from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import settings


class LLMConfigError(RuntimeError):
    """Raised when LLM configuration is missing."""


class LLMResponseError(RuntimeError):
    """Raised when the LLM response cannot be parsed."""


def extract_json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        parts = candidate.split("```")
        for part in parts:
            snippet = part.strip()
            if snippet.startswith("json"):
                snippet = snippet[4:].strip()
            if snippet.startswith("{") and snippet.endswith("}"):
                candidate = snippet
                break

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMResponseError("模型没有返回有效的 JSON 内容。")

    try:
        return json.loads(candidate[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMResponseError("模型返回的 JSON 解析失败。") from exc


class DeepSeekClient:
    async def complete_text(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        if not settings.is_llm_configured:
            raise LLMConfigError("未检测到 DEEPSEEK_API_KEY，请先配置环境变量。")

        url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": settings.deepseek_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()

        data = response.json()
        try:
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError("模型响应缺少内容字段。") from exc

    async def complete_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> dict[str, Any]:
        if not settings.is_llm_configured:
            raise LLMConfigError("未检测到 DEEPSEEK_API_KEY，请先配置环境变量。")

        url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": settings.deepseek_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()

        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError("模型响应缺少内容字段。") from exc
        return extract_json_object(content)
