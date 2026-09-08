from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import date
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings
from app.nl_analytics import (
    ANALYSIS_TYPES,
    COMPARISON_MODES,
    DIMENSIONS,
    ENTITY_FILTER_KEYS,
    METRICS,
    normalize_analysis_intent_v2,
)


logger = logging.getLogger("ark_analytics")


def ark_analytics_enabled() -> bool:
    return settings.ark_analytics_enabled and bool(settings.ark_api_key and settings.ark_model)


def parse_analytics_intent(question: str) -> dict[str, Any] | None:
    if not ark_analytics_enabled():
        return None

    payload = {
        "model": settings.ark_model,
        "temperature": 0,
        "max_tokens": 900,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是订单经营分析意图解析器。只返回一个 JSON 对象，不得返回 Markdown，不得生成 SQL。"
                    f"服务器当前日期是 {date.today().isoformat()}，所有相对日期必须据此换算。"
                    "JSON 必须包含：version='2'；analysis_type；time_range{start_time,end_time,label}；"
                    "comparison{mode}；filters；filter_hints；dimensions；metrics；order_metric；"
                    "wants_share；sort_direction；limit；confidence；assumptions；clarifications；narrative_goal。"
                    f"analysis_type 只能是: {', '.join(sorted(ANALYSIS_TYPES))}。"
                    f"comparison.mode 只能是: {', '.join(sorted(COMPARISON_MODES))}。"
                    f"Allowed dimensions: {', '.join(DIMENSIONS)}. "
                    f"Allowed metrics: {', '.join(METRICS)}. "
                    f"Allowed filter keys: {', '.join(ENTITY_FILTER_KEYS)} and order_no. "
                    "filters 仅填写用户明确给出的精确值；口语中的平台、区域、分类、店铺、产品等实体原文"
                    "放进 filter_hints，稍后由服务端匹配真实数据。不要虚构业务值。"
                    "日期必须为 YYYY-MM-DD。同比使用 year_over_year，环比或相比上一周期使用 previous_period。"
                    "如果存在冲突或重要歧义，在 clarifications 中写简短说明，并降低 confidence。"
                    "禁止索取或推断个人敏感信息。"
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
    return normalize_analysis_intent_v2(dict(raw_intent), question)


def synthesize_analytics_answer(
    question: str,
    intent: dict[str, Any],
    insights: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> str | None:
    if not ark_analytics_enabled():
        return None
    safe_rows = rows[:20]
    payload = {
        "model": settings.ark_model,
        "temperature": 0.1,
        "max_tokens": 450,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是经营分析助手。根据给出的结构化意图、聚合数据和确定性发现，"
                    "用中文输出一段不超过 220 字的结论。必须引用数据中的事实，不能虚构原因，"
                    "无法由数据证明的内容要表述为建议核查项。不要输出 Markdown、SQL、个人敏感信息或思维过程。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": question,
                        "intent": {
                            "analysis_type": intent.get("analysis_type"),
                            "time_range": intent.get("time_range"),
                            "comparison": intent.get("comparison"),
                            "filters": intent.get("filters"),
                            "dimensions": intent.get("dimensions"),
                            "metrics": intent.get("metrics"),
                        },
                        "insights": insights,
                        "aggregated_rows": safe_rows,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            },
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
        logger.warning("Ark analytics synthesis failed: %s", exc)
        return None
    content = extract_message_content(body)
    return content[:500] if content else None


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
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, Mapping) and item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts).strip()
    return ""


def strip_code_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    return text.strip()
