"""Writes a recommended title and description per clip, saved as a .txt next to the clip."""
import json
import re
from pathlib import Path

from .agent import run_agent
from .jsonutil import parse_json
from .models import registry
from .skills import load_skill


def generate(*, platform: str, transcript: str, hook: str = "", trends: dict | None = None,
             web_search_enabled: bool = False, model: str | None = None) -> dict:
    entry = registry.resolve(model or "refiner")
    user = f"Platform: {platform}\nHook: {hook}\n\nClip transcript:\n{transcript[:6000]}"
    if trends:
        user += "\n\nTrend context:\n" + json.dumps(
            {"videos": [v["title"] for v in trends.get("videos", [])]}, ensure_ascii=False)[:2000]
    messages = [{"role": "system", "content": load_skill("write-metadata")},
                {"role": "user", "content": user}]
    res = run_agent(entry["id"], messages, web_search_enabled=web_search_enabled, json_mode=True)
    meta = parse_json(res["text"]) or {"title": "", "description": "", "hashtags": []}
    return {"meta": meta, "usage": res["usage"], "searches": res["searches"], "model": res["model"]}


def write_text_file(path: Path, platform: str, meta: dict) -> Path:
    """Save the recommended metadata as a plain .txt the creator can copy when posting."""
    tags = " ".join("#" + t.lstrip("#") for t in meta.get("hashtags", []))
    alts = "\n".join(f"  - {t}" for t in meta.get("alt_titles", []))
    body = (
        f"PLATFORM: {platform}\n\n"
        f"TITLE:\n{meta.get('title', '')}\n\n"
        f"ALTERNATIVE TITLES:\n{alts or '  (none)'}\n\n"
        f"DESCRIPTION:\n{meta.get('description', '')}\n\n"
        f"HASHTAGS:\n{tags}\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path
