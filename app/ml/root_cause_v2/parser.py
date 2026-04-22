"""
LLM response parser.

The LLM is prompted to emit a strict JSON object. Real-world LLM output
often comes wrapped in markdown fences, has trailing commentary, or
omits fields. This parser:

  1. Extracts the first JSON object from the raw text (tolerates fences).
  2. Validates the schema and types.
  3. Coerces what's safe; rejects what isn't.
  4. Raises `ParseError` (subclass of `MLEngineException`) on failure.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.core import MLEngineException, get_logger
from app.ml.root_cause_v2.types import LLMRootCauseResponse

logger = get_logger(__name__)

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class ParseError(MLEngineException):
    """LLM output failed to parse."""

    error_code = "LLM_PARSE_ERROR"


def parse_llm_response(raw: str) -> LLMRootCauseResponse:
    """Parse and validate an LLM response into `LLMRootCauseResponse`."""
    if not raw or not raw.strip():
        raise ParseError("LLM returned empty response")

    cleaned = _strip_fences(raw)
    obj = _extract_json_object(cleaned)

    return LLMRootCauseResponse(
        probable_cause=_get_str(obj, "probable_cause", required=True, max_len=200),
        confidence=_get_confidence(obj),
        details=_get_str(obj, "details", required=True, max_len=2000),
        recommended_actions=_get_str_list(obj, "recommended_actions", required=True),
        referenced_incident_ids=_get_str_list(obj, "referenced_incident_ids", required=False),
        reasoning=_get_str(obj, "reasoning", required=False, max_len=1000) or "",
    )


# ---------------- helpers ----------------

def _strip_fences(text: str) -> str:
    """Remove surrounding ```json ... ``` fences if present."""
    text = text.strip()
    if text.startswith("```"):
        # drop opening fence
        text = re.sub(r"^```(?:json)?\s*", "", text)
        # drop closing fence
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_json_object(text: str) -> dict:
    """Find and parse the first top-level JSON object in `text`."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = _JSON_OBJECT_RE.search(text)
    if not match:
        raise ParseError(
            "No JSON object found in LLM response",
            details={"raw_preview": text[:200]},
        )
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ParseError(
            "Found JSON-like text but it failed to parse",
            details={"underlying": str(exc), "raw_preview": text[:200]},
        ) from exc


def _get_str(
    obj: dict,
    key: str,
    *,
    required: bool,
    max_len: int = 1000,
) -> str | None:
    val = obj.get(key)
    if val is None:
        if required:
            raise ParseError(f"Missing required field: {key}")
        return None
    if not isinstance(val, str):
        raise ParseError(
            f"Field {key} must be a string",
            details={"actual_type": type(val).__name__},
        )
    val = val.strip()
    if required and not val:
        raise ParseError(f"Required field is empty: {key}")
    if len(val) > max_len:
        logger.warning("llm_field_truncated", field=key, original_len=len(val))
        val = val[:max_len]
    return val


def _get_confidence(obj: dict) -> float:
    val: Any = obj.get("confidence")
    if val is None:
        raise ParseError("Missing required field: confidence")
    try:
        f = float(val)
    except (TypeError, ValueError) as exc:
        raise ParseError(
            "confidence must be a number between 0.0 and 1.0",
            details={"actual": repr(val)},
        ) from exc
    # Clamp instead of reject — LLMs sometimes emit 1.05 or -0.01
    return max(0.0, min(1.0, f))


def _get_str_list(obj: dict, key: str, *, required: bool) -> list[str]:
    val = obj.get(key, [])
    if val is None:
        val = []
    if not isinstance(val, list):
        if required:
            raise ParseError(
                f"Field {key} must be a list",
                details={"actual_type": type(val).__name__},
            )
        return []
    out: list[str] = []
    for i, item in enumerate(val):
        if not isinstance(item, str):
            logger.warning(
                "llm_list_item_skipped_non_string",
                key=key,
                index=i,
                actual_type=type(item).__name__,
            )
            continue
        item = item.strip()
        if item:
            out.append(item)
    if required and not out:
        raise ParseError(f"Required list field is empty: {key}")
    return out
