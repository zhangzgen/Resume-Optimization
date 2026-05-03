from __future__ import annotations

import json
from typing import Any, AsyncIterator

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


def _build_url() -> str:
    return f"{settings.xiaomi_base_url.rstrip('/')}/chat/completions"


def _build_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.xiaomi_api_key}",
        "Content-Type": "application/json",
    }


class MiMoClient:
    async def complete_text(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        if not settings.is_llm_configured:
            raise LLMConfigError("未检测到 XIAOMI_API_KEY，请先配置环境变量。")

        payload = {
            "model": settings.xiaomi_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.post(_build_url(), json=payload, headers=_build_headers())
            response.raise_for_status()

        data = response.json()
        try:
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError("模型响应缺少内容字段。") from exc

    async def complete_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> dict[str, Any]:
        if not settings.is_llm_configured:
            raise LLMConfigError("未检测到 XIAOMI_API_KEY，请先配置环境变量。")

        payload = {
            "model": settings.xiaomi_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.post(_build_url(), json=payload, headers=_build_headers())
            response.raise_for_status()

        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError("模型响应缺少内容字段。") from exc
        return extract_json_object(content)

    async def stream_text(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> AsyncIterator[str]:
        """Stream text chunks from the LLM in real-time."""
        if not settings.is_llm_configured:
            raise LLMConfigError("未检测到 XIAOMI_API_KEY，请先配置环境变量。")

        payload = {
            "model": settings.xiaomi_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            async with client.stream("POST", _build_url(), json=payload, headers=_build_headers()) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    raise LLMResponseError(f"API 返回错误 {response.status_code}: {body.decode(errors='replace')[:200]}")

                buffer = ""
                async for raw_chunk in response.aiter_text():
                    buffer += raw_chunk
                    while True:
                        line_end = buffer.find("\n")
                        if line_end == -1:
                            break
                        line = buffer[:line_end].strip()
                        buffer = buffer[line_end + 1:]
                        if not line or line == "data: [DONE]":
                            continue
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except (json.JSONDecodeError, IndexError):
                                continue

                # Flush all remaining lines in buffer
                for remaining_line in buffer.split("\n"):
                    remaining_line = remaining_line.strip()
                    if not remaining_line or remaining_line == "data: [DONE]":
                        continue
                    if remaining_line.startswith("data: "):
                        try:
                            data = json.loads(remaining_line[6:])
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except (json.JSONDecodeError, IndexError):
                            continue
