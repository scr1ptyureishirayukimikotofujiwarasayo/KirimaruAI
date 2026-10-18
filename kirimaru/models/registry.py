"""Model registry: maps roles to OpenRouter model IDs and supports user-added models."""
import json
from pathlib import Path

REGISTRY_PATH = Path(__file__).with_name("registry.json")
USER_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "models.user.json"


def _load(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8-sig"))
    return {}


def load_registry() -> dict:
    base = _load(REGISTRY_PATH)
    user = _load(USER_REGISTRY_PATH)
    base.setdefault("models", {}).update(user.get("models", {}))
    base.setdefault("roles", {}).update(user.get("roles", {}))
    if "default_role" in user:
        base["default_role"] = user["default_role"]
    return base


def resolve(role_or_key: str | None = None) -> dict:
    """Return the model entry for a role name or model key (or the default role)."""
    reg = load_registry()
    key = role_or_key or reg["default_role"]
    key = reg["roles"].get(key, key)
    if key not in reg["models"]:
        raise KeyError(f"Unknown model role/key: {role_or_key!r}. Known: {list(reg['models'])}")
    return reg["models"][key]


def supports(entry: dict, modality: str) -> bool:
    return modality in entry.get("modalities", [])


def add_user_model(key: str, model_id: str, modalities: list[str], notes: str = "") -> None:
    """Persist a user-added model (e.g. any OpenRouter video/audio model)."""
    user = _load(USER_REGISTRY_PATH)
    user.setdefault("models", {})[key] = {
        "id": model_id,
        "modalities": modalities,
        "max_input_tokens": 200000,
        "notes": notes,
    }
    USER_REGISTRY_PATH.write_text(json.dumps(user, indent=2), encoding="utf-8")

