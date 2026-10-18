"""Web search via DuckDuckGo (no API key). Finds videos/trends for a topic or genre."""
from ddgs import DDGS


def search_videos(query: str, max_results: int = 10) -> list[dict]:
    with DDGS() as ddgs:
        results = ddgs.videos(query, max_results=max_results) or []
    return [{
        "title": r.get("title"),
        "url": r.get("url") or r.get("embed_url") or r.get("content"),
        "duration": r.get("duration"),
        "publisher": r.get("publisher"),
        "published": r.get("published"),
        "views": (r.get("statistics") or {}).get("viewCount"),
    } for r in results]


def search_web(query: str, max_results: int = 8) -> list[dict]:
    with DDGS() as ddgs:
        results = ddgs.text(query, max_results=max_results) or []
    return [{"title": r.get("title"), "url": r.get("href"), "snippet": r.get("body")} for r in results]


def trend_brief(topic: str) -> dict:
    """Gather what's currently getting engagement for a topic: viral videos + web discussion."""
    return {
        "topic": topic,
        "videos": search_videos(f"{topic} viral shorts clips", 10),
        "web": search_web(f"{topic} trending viral clips engagement", 8),
    }
