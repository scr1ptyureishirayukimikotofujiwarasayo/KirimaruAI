"""Loads skill markdown files: front-matter + body becomes the system prompt."""
from pathlib import Path

SKILLS_DIR = Path(__file__).parent


def load_skill(name: str) -> str:
    text = (SKILLS_DIR / f"{name}.md").read_text(encoding="utf-8-sig")
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    return text.strip()


