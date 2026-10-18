"""Fetch the live OpenRouter model catalog using your API key and cache it locally."""
import json
import time
import urllib.request
from pathlib import Path

from .. import openrouter

CACHE_PATH = Path(__file__).resolve().parents[2] / "output" / "models_cache.json"
CACHE_TTL = 6 * 3600
MODELS_URL = "https://openrouter.ai/api/v1/models"


def _fetch_remote() -> list[dict]:
    req = urllib.request.Request(MODELS_URL, headers={"Authorization": f"Bearer {openrouter._key()}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8")).get("data", [])


def _simplify(m: dict) -> dict:
    arch = m.get("architecture") or {}
    pricing = m.get("pricing") or {}
    return {
        "id": m["id"],
        "name": m.get("name", m["id"]),
        "context_length": m.get("context_length"),
        "input_modalities": arch.get("input_modalities") or [],
        "output_modalities": arch.get("output_modalities") or [],
        "prompt_price": float(pricing.get("prompt", 0) or 0),
        "completion_price": float(pricing.get("completion", 0) or 0),
    }


def get_models(refresh: bool = False) -> list[dict]:
    """Return simplified OpenRouter models, using a 6h cache unless refresh=True."""
    if not refresh and CACHE_PATH.exists() and time.time() - CACHE_PATH.stat().st_mtime < CACHE_TTL:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    models = [_simplify(m) for m in _fetch_remote()]
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(models, indent=2), encoding="utf-8")
    return models


def filter_models(models: list[dict], *, modality: str | None = None, search: str | None = None) -> list[dict]:
    out = models
    if modality:
        out = [m for m in out if modality in m["input_modalities"]]
    if search:
        s = search.lower()
        out = [m for m in out if s in m["id"].lower() or s in m["name"].lower()]
    return out
