from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings


logger = logging.getLogger("coding_plan")


class ArkCodingError(RuntimeError):
    """A safe error message that can be returned by the chat API."""


def coding_chat_enabled() -> bool:
    return settings.ark_coding_chat_enabled and bool(settings.ark_api_key and settings.ark_model)


def ask_coding_plan(messages: list[dict[str, str]]) -> dict[str, Any]:
    if not coding_chat_enabled():
        raise ArkCodingError("Coding Plan 服务尚未配置，请在服务端设置 ARK_CODING_CHAT_ENABLED、ARK_API_KEY 和 ARK_MODEL。")

    payload = {
        "model": settings.ark_model,
        "temperature": 0.2,
        "max_tokens": max(256, min(settings.ark_coding_max_output_tokens, 4096)),
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是专业的中文编程助手。优先给出可执行、可验证的方案；"
                    "代码示例要简洁并说明修改位置。不要编造运行结果、链接或文件内容。"
                ),
            },
            *messages,
        ],
    }
    request = Request(
        f"{settings.ark_base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.ark_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=max(1, settings.ark_timeout_seconds)) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        logger.warning("Ark Coding Plan request failed with HTTP %s", exc.code)
        raise ArkCodingError("方舟服务暂时不可用，请稍后重试。") from exc
    except (URLError, TimeoutError) as exc:
        logger.warning("Ark Coding Plan network request failed: %s", type(exc).__name__)
        raise ArkCodingError("无法连接方舟服务，请检查网关地址、网络和超时配置。") from exc
    except json.JSONDecodeError as exc:
        logger.warning("Ark Coding Plan returned invalid JSON")
        raise ArkCodingError("方舟服务返回了无法解析的响应。") from exc

    content = _extract_content(body)
    if not content:
        raise ArkCodingError("方舟服务未返回有效的对话内容。")
    usage = body.get("usage") if isinstance(body, Mapping) else None
    return {"content": content, "usage": usage if isinstance(usage, Mapping) else {}, "model": settings.ark_model}


def _extract_content(body: Any) -> str:
    if not isinstance(body, Mapping):
        return ""
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        return ""
    message = choices[0].get("message")
    if not isinstance(message, Mapping):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "".join(
            item.get("text", "") for item in content if isinstance(item, Mapping) and isinstance(item.get("text"), str)
        ).strip()
    return ""
