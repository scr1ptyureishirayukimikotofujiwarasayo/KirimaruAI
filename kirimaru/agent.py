"""Agent loop with tool calling. The model can call web_search on its own when enabled."""
import json

from . import openrouter
from .tools import search

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web (DuckDuckGo) for current trends, examples or facts. Use only when it would materially improve the answer.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query"}},
            "required": ["query"],
        },
    },
}


def run_agent(model_id: str, messages: list[dict], *, web_search_enabled: bool,
              max_steps: int = 4, json_mode: bool = False, max_tokens: int = 2000) -> dict:
    """Run chat with optional tool use. Returns final text, usage and the searches performed."""
    searches = []
    tools = [WEB_SEARCH_TOOL] if web_search_enabled else None
    total_usage = {}
    for _ in range(max_steps):
        res = openrouter.chat_raw(model_id, messages, tools=tools, json_mode=json_mode and not tools,
                                  max_tokens=max_tokens)
        for k, v in (res.get("usage") or {}).items():
            if isinstance(v, (int, float)):
                total_usage[k] = total_usage.get(k, 0) + v
        msg = res["message"]
        calls = msg.get("tool_calls") or []
        if not calls:
            return {"text": msg.get("content") or "", "usage": total_usage, "searches": searches, "model": res["model"]}
        messages.append(msg)
        for call in calls:
            args = json.loads(call["function"]["arguments"] or "{}")
            query = args.get("query", "")
            searches.append(query)
            results = search.search_web(query, 5)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(results, ensure_ascii=False)})
    return {"text": "", "usage": total_usage, "searches": searches, "model": model_id,
            "error": "max tool steps reached"}
