"""Command line. Examples:
  python -m kirimaru models                       # configured roles and models
  python -m kirimaru models --fetch --modality video   # live OpenRouter catalog (uses your key)
  python -m kirimaru run <url> [--genre "..."] [--max-clips 5] [--budget 0.50] [--multimodal]
  python -m kirimaru trends "<topic>"              # DuckDuckGo video + web trend search
  python -m kirimaru add-model <key> <openrouter-id> --modalities text,video
  python -m kirimaru web
  python -m kirimaru connect youtube        # log in once in a visible browser
  python -m kirimaru accounts               # show connected platforms
  python -m kirimaru analyze --platform youtube --title "..." --description "..." --hook "..." --transcript-file t.txt [--web-search]
"""
import argparse
import json
import os
import sys
from pathlib import Path

from . import pipeline
from .models import catalog, registry
from .tools import search


def _load_env() -> None:
    env = Path(__file__).resolve().parents[1] / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def main(argv: list[str] | None = None) -> int:
    _load_env()
    ap = argparse.ArgumentParser(prog="kirimaru")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="Find clips in a video URL")
    r.add_argument("url")
    r.add_argument("--max-clips", type=int, default=5)
    r.add_argument("--budget", type=float, default=1.0, help="Max USD to spend")
    r.add_argument("--multimodal", action="store_true", help="Use audio/video model instead of transcript")
    r.add_argument("--scorer", help="Model role or key for cheap scoring")
    r.add_argument("--refiner", help="Model role or key for final picks")
    r.add_argument("--multimodal-model", help="Model role or key for audio/video")
    r.add_argument("--genre", help="Topic/genre; web search adds trend context to the picks")
    r.add_argument("--platform", default="youtube", help="Target platform for titles/descriptions")
    r.add_argument("--no-title-card", action="store_true", help="Do not burn the title onto the clip")
    r.add_argument("--no-metadata", action="store_true", help="Skip writing the post .txt files")
    r.add_argument("--web-search", action="store_true", help="Let the metadata writer use DuckDuckGo")

    mo = sub.add_parser("models", help="List configured roles, or fetch the live OpenRouter catalog")
    mo.add_argument("--fetch", action="store_true", help="Fetch live OpenRouter catalog with your API key")
    mo.add_argument("--modality", help="Filter fetched models by input modality (text,image,audio,video)")
    mo.add_argument("--search", help="Filter fetched models by name/id")
    mo.add_argument("--refresh", action="store_true", help="Ignore the 6h cache")

    tr = sub.add_parser("trends", help="Search DuckDuckGo videos and web for a topic")
    tr.add_argument("topic")

    a = sub.add_parser("add-model", help="Register an OpenRouter model")
    a.add_argument("key")
    a.add_argument("model_id")
    a.add_argument("--modalities", default="text", help="comma list: text,image,audio,video")
    a.add_argument("--notes", default="")

    sub.add_parser("web", help="Start the local web UI")

    tt = sub.add_parser("titles", help="Write a title and description .txt for a transcript or hook")
    tt.add_argument("--platform", default="youtube")
    tt.add_argument("--hook", default="")
    tt.add_argument("--transcript-file", required=True)
    tt.add_argument("--out", required=True, help="Path of the .txt to write")
    tt.add_argument("--web-search", action="store_true")

    cn = sub.add_parser("connect", help="Log in to a platform in a visible browser (saved locally)")
    cn.add_argument("platform", choices=["youtube", "tiktok", "instagram", "twitch"])
    cn.add_argument("--disconnect", action="store_true", help="Remove the saved session instead")

    sub.add_parser("accounts", help="Show which platforms have a saved session")

    an = sub.add_parser("analyze", help="AI review of title, description, hook and transcript")
    an.add_argument("--platform", required=True)
    an.add_argument("--title", default="")
    an.add_argument("--description", default="")
    an.add_argument("--hook", default="")
    an.add_argument("--transcript-file", help="Path to a text file with the transcript")
    an.add_argument("--web-search", action="store_true", help="Let the AI use DuckDuckGo search")
    an.add_argument("--model", help="Model role or key (default: refiner)")

    args = ap.parse_args(argv)

    if args.cmd == "run":
        result = pipeline.run(args.url, max_clips=args.max_clips, budget_usd=args.budget,
                              multimodal=args.multimodal, scorer=args.scorer,
                              refiner=args.refiner, multimodal_model=args.multimodal_model,
                              genre=args.genre, platform=args.platform,
                              title_cards=not args.no_title_card,
                              write_metadata=not args.no_metadata,
                              web_search=args.web_search)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.cmd == "models":
        if args.fetch:
            models = catalog.filter_models(catalog.get_models(refresh=args.refresh),
                                           modality=args.modality, search=args.search)
            for m in models:
                price = f"${m['prompt_price'] * 1e6:.2f}/${m['completion_price'] * 1e6:.2f} per M"
                print(f"{m['id']:<50} in={','.join(m['input_modalities'])}  ctx={m['context_length']}  {price}")
            print(f"\n{len(models)} models")
        else:
            print(json.dumps(registry.load_registry(), indent=2))
    elif args.cmd == "trends":
        print(json.dumps(search.trend_brief(args.topic), indent=2, ensure_ascii=False))
    elif args.cmd == "connect":
        from . import accounts
        if args.disconnect:
            accounts.disconnect(args.platform)
            print(f"Disconnected {args.platform}.")
        else:
            accounts.connect(args.platform)
    elif args.cmd == "accounts":
        from . import accounts
        print(json.dumps(accounts.status(), indent=2))
    elif args.cmd == "analyze":
        from . import analyze as an_mod
        transcript = Path(args.transcript_file).read_text(encoding="utf-8-sig") if args.transcript_file else ""
        result = an_mod.analyze(platform=args.platform, title=args.title, description=args.description,
                                hook=args.hook, transcript=transcript,
                                web_search_enabled=args.web_search, model=args.model)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.cmd == "titles":
        from .metadata import generate, write_text_file
        transcript = Path(args.transcript_file).read_text(encoding="utf-8-sig")
        gen = generate(platform=args.platform, transcript=transcript, hook=args.hook,
                       web_search_enabled=args.web_search)
        path = write_text_file(Path(args.out), args.platform, gen["meta"])
        print(json.dumps(gen["meta"], indent=2, ensure_ascii=False))
        print(f"Wrote {path}")
    elif args.cmd == "add-model":
        registry.add_user_model(args.key, args.model_id, args.modalities.split(","), args.notes)
        print(f"Added {args.key} -> {args.model_id}")
    elif args.cmd == "web":
        from .web.server import serve
        serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())


