"""OpenRouter client. Uses only OpenRouter API keys (OPENROUTER_API_KEY)."""
import base64
import json
import os
import urllib.request
import urllib.error

API_URL = "https://openrouter.ai/api/v1/chat/completions"


def _key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set. Put it in .env or your environment.")
    return key


def chat_raw(model_id: str, messages: list[dict], *, tools: list[dict] | None = None,
             json_mode: bool = False, max_tokens: int = 2000, temperature: float = 0.3) -> dict:
    """Low-level call. Returns the full assistant message (may contain tool_calls) and usage."""
    body = {"model": model_id, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    if tools:
        body["tools"] = tools
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_key()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost/kirimaru",
            "X-Title": "KirimaruAI",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"OpenRouter error {e.code}: {e.read().decode('utf-8', 'replace')}") from e
    choice = data["choices"][0]
    return {"message": choice["message"], "model": data.get("model", model_id), "usage": data.get("usage", {})}


def chat(model_id: str, messages: list[dict], *, json_mode: bool = False,
         max_tokens: int = 2000, temperature: float = 0.3) -> dict:
    res = chat_raw(model_id, messages, json_mode=json_mode, max_tokens=max_tokens, temperature=temperature)
    return {"text": res["message"].get("content") or "", "model": res["model"], "usage": res["usage"]}


def file_part_b64(path: str, mime: str) -> dict:
    """Build an inline media content part (for audio/video-capable models)."""
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    if mime.startswith("audio/"):
        return {"type": "input_audio", "input_audio": {"data": b64, "format": mime.split("/")[1]}}
    return {"type": "file", "file": {"filename": os.path.basename(path), "file_data": f"data:{mime};base64,{b64}"}}
