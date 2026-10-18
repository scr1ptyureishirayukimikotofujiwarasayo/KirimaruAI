"""Post analysis: reviews title, description, hook and transcript and suggests improvements."""
import json
import re

from .agent import run_agent
from .jsonutil import parse_json
from .models import registry
from .skills import load_skill


def analyze(*, platform: str, title: str, description: str, hook: str,
            transcript: str, web_search_enabled: bool, model: str | None = None) -> dict:
    entry = registry.resolve(model or "refiner")
    user = (f"Platform: {platform}\nTitle: {title}\nDescription: {description}\n"
            f"Hook: {hook}\n\nTranscript:\n{transcript[:12000]}")
    messages = [
        {"role": "system", "content": load_skill("analyze-post")},
        {"role": "user", "content": user},
    ]
    res = run_agent(entry["id"], messages, web_search_enabled=web_search_enabled, json_mode=True)
    report = parse_json(res["text"]) or {"error": "model returned no JSON", "raw": res["text"]}
    return {"report": report, "searches": res["searches"], "usage": res["usage"], "model": res["model"]}
