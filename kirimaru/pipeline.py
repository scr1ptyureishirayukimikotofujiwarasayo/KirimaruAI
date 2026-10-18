"""Pipeline: cheapest path first. Captions -> cheap scoring -> strong refine -> cut.
Multimodal model only when there is no transcript or explicitly requested."""
import json
import re
from pathlib import Path

from . import openrouter
from .jsonutil import parse_json
from .models import registry
from .skills import load_skill
from .tools import media, search
from .tools.budget import Budget

OUT_ROOT = Path(__file__).resolve().parents[1] / "output"


def _json(text: str) -> dict:
    return parse_json(text)


def run(url: str, *, max_clips: int = 5, budget_usd: float = 1.0,
        multimodal: bool = False, scorer: str | None = None,
        refiner: str | None = None, multimodal_model: str | None = None,
        genre: str | None = None, platform: str = "youtube",
        title_cards: bool = True, write_metadata: bool = True,
        web_search: bool = False) -> dict:
    budget = Budget(max_usd=budget_usd)
    trends = search.trend_brief(genre) if genre else None
    info = media.fetch_info(url)
    job = OUT_ROOT / (info["id"] or "job")
    job.mkdir(parents=True, exist_ok=True)
    (job / "info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

    segments = []
    vtt = None if multimodal else media.fetch_captions(url, job)
    if vtt:
        segments = media.parse_vtt(vtt)

    if segments:
        chunks = media.chunk_segments(segments)
        scorer_entry = registry.resolve(scorer or "scorer")
        scores = _score(chunks, scorer_entry, budget)
        top = [c for c in scores if c["score"] >= 6]
        top_chunks = sorted(top, key=lambda c: -c["score"])[:12]
        top_chunks.sort(key=lambda c: c["start"])
        refined = _refine(top_chunks, max_clips, registry.resolve(refiner or "refiner"), budget, trends)
        mode = "transcript"
    else:
        media_path = media.download_media(url, job)
        entry = registry.resolve(multimodal_model or "multimodal")
        if not registry.supports(entry, "video"):
            raise RuntimeError(f"Model {entry['id']} does not support video input.")
        refined = _multimodal(media_path, max_clips, entry, budget)
        mode = "multimodal"

    existing = list(job.glob("source.*"))
    source = existing[0] if existing else media.download_media(url, job)
    results = []
    from .metadata import generate, write_text_file
    for i, c in enumerate(refined[:max_clips], 1):
        raw = media.cut_clip(source, float(c["start"]), float(c["end"]), job / f"clip_{i:02d}_raw.mp4")
        title = c.get("title", f"Clip {i}")
        final = raw
        if title_cards:
            final = media.burn_title(raw, title, job / f"clip_{i:02d}.mp4")
            raw.unlink(missing_ok=True)
        else:
            raw.rename(job / f"clip_{i:02d}.mp4")
            final = job / f"clip_{i:02d}.mp4"
        entry_out = {**c, "file": str(final)}
        if write_metadata:
            clip_text = " ".join(s["text"] for s in segments
                                 if s["start"] >= float(c["start"]) and s["end"] <= float(c["end"]))
            if not clip_text:
                clip_text = " ".join(filter(None, [c.get("hook", ""), c.get("why", "")]))
            gen = generate(platform=platform, transcript=clip_text, hook=c.get("hook", ""),
                           trends=trends, web_search_enabled=web_search,
                           model=None)
            budget.record(gen["model"], gen["usage"])
            entry_out["metadata"] = gen["meta"]
            entry_out["metadata_file"] = str(write_text_file(
                job / f"clip_{i:02d}_post.txt", platform, gen["meta"]))
        results.append(entry_out)
    (job / "clips.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"mode": mode, "clips": results, "spent_usd": round(budget.spent_usd, 5),
            "output": str(job), "trends": trends}


def _score(chunks: list[dict], entry: dict, budget: Budget) -> list[dict]:
    system = load_skill("score-transcript")
    scored = []
    batch = 20
    for b in range(0, len(chunks), batch):
        part = chunks[b:b + batch]
        payload = "\n".join(f"[{b + i}] {c['start']:.0f}-{c['end']:.0f}s: {c['text']}" for i, c in enumerate(part))
        res = openrouter.chat(entry["id"], [
            {"role": "system", "content": system},
            {"role": "user", "content": payload},
        ], json_mode=True, max_tokens=1200)
        budget.record(entry["id"], res["usage"])
        for item in _json(res["text"]).get("chunks", []):
            idx = int(item["index"])
            if 0 <= idx < len(chunks):
                scored.append({**chunks[idx], "score": float(item["score"]), "reason": item.get("reason", "")})
    return scored


def _refine(top: list[dict], n: int, entry: dict, budget: Budget, trends: dict | None = None) -> list[dict]:
    payload = f"Pick up to {n} clips.\n\n"
    if trends:
        context = {"videos": [v["title"] for v in trends["videos"]], "web": [w["snippet"] for w in trends["web"]]}
        payload += "Audience trend context for this genre (what currently performs):\n"
        payload += json.dumps(context, ensure_ascii=False)[:3000] + "\n\n"
    payload += "\n".join(f"{c['start']:.0f}-{c['end']:.0f}s (score {c['score']}): {c['text']}" for c in top)
    res = openrouter.chat(entry["id"], [
        {"role": "system", "content": load_skill("refine-clips")},
        {"role": "user", "content": payload},
    ], json_mode=True, max_tokens=2000)
    budget.record(entry["id"], res["usage"])
    return _json(res["text"]).get("clips", [])


def _multimodal(media_path: Path, n: int, entry: dict, budget: Budget) -> list[dict]:
    size_mb = media_path.stat().st_size / (1024 * 1024)
    if size_mb > 200:
        raise RuntimeError(
            f"Video is {size_mb:.0f} MB, too large to send to a multimodal model inline. "
            "Re-run without --multimodal (captions) or trim the source first.")
    part = openrouter.file_part_b64(str(media_path), "video/mp4")
    res = openrouter.chat(entry["id"], [
        {"role": "system", "content": load_skill("multimodal-moments")},
        {"role": "user", "content": [
            {"type": "text", "text": f"Find up to {n} clips."}, part]},
    ], json_mode=True, max_tokens=2000)
    budget.record(entry["id"], res["usage"])
    return _json(res["text"]).get("clips", [])
