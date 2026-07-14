from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings
from app.nl_analytics import DIMENSIONS, METRICS, normalize_analysis_intent


logger = logging.getLogger("ark_analytics")


def ark_analytics_enabled() -> bool:
    return settings.ark_analytics_enabled and bool(settings.ark_api_key and settings.ark_model)


def parse_analytics_intent(question: str) -> dict[str, Any] | None:
    if not ark_analytics_enabled():
        return None

    payload = {
        "model": settings.ark_model,
        "temperature": 0,
        "max_tokens": 240,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You classify e-commerce analytics questions. Return JSON only, with keys "
                    "dimensions (array), metrics (array), order_metric (string), wants_share (boolean). "
                    f"Allowed dimensions: {', '.join(DIMENSIONS)}. "
                    f"Allowed metrics: {', '.join(METRICS)}. "
                    "Never generate SQL. Do not request or infer personal data. "
                    "Use only allowed values. If uncertain, return empty arrays and false."
                ),
            },
            {"role": "user", "content": question},
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
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("Ark intent parsing failed: %s", exc)
        return None

    content = extract_message_content(body)
    if not content:
        logger.warning("Ark intent parsing returned no message content")
        return None
    try:
        raw_intent = json.loads(strip_code_fence(content))
    except json.JSONDecodeError:
        logger.warning("Ark intent parsing returned non-JSON content")
        return None
    if not isinstance(raw_intent, Mapping):
        return None
    return normalize_analysis_intent(dict(raw_intent))


def extract_message_content(body: Any) -> str:
    if not isinstance(body, Mapping):
        return ""
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        return ""
    message = choices[0].get("message")
    if not isinstance(message, Mapping):
        return ""
    content = message.get("content")
    return content.strip() if isinstance(content, str) else ""


def strip_code_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    return text.strip()
