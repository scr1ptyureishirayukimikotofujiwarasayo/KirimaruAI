"""Robust JSON extraction from model output (handles code fences, prose, trailing commas)."""
import json
import re

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)


def parse_json(text: str) -> dict:
    """Best-effort JSON object extraction from a model reply. Returns {} on failure."""
    if not text:
        return {}
    m = _FENCE.search(text)
    if m:
        text = m.group(1)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    candidate = m.group(0)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    # Strip trailing commas, a common model slip, and retry.
    try:
        return json.loads(re.sub(r",\s*([}\]])", r"\1", candidate))
    except json.JSONDecodeError:
        return {}
