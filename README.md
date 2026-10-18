# KirimaruAI

AI clipping tool. Finds short clips in YouTube, Twitch, TikTok, Instagram and any yt-dlp-supported site.
Uses **only OpenRouter** for AI, so one API key covers every model.

## Cost-first design
1. Captions (free via yt-dlp) -> transcript chunks
2. Cheap model scores every chunk (`scorer`)
3. Strong model picks final clips from top chunks only (`refiner`)
4. Multimodal model (audio/video) only if there are no captions or you ask for it
5. A per-run `--budget` stops the run before overspending

## Setup
1. Install: `pip install -r requirements.txt`, plus `ffmpeg` on PATH.
2. Copy `.env.example` to `.env` and add your `OPENROUTER_API_KEY`.

## Usage
```
python -m kirimaru models
python -m kirimaru run "https://www.youtube.com/watch?v=..." --max-clips 5 --budget 0.50
python -m kirimaru run "<url>" --multimodal
python -m kirimaru add-model my_video_model vendor/model-id --modalities text,audio,video
python -m kirimaru web        # http://127.0.0.1:8765
```

## Model system
- `kirimaru/models/registry.json`: built-in roles and models. Roles (`scorer`, `refiner`, `multimodal`, `router`) point at model keys.
- `models.user.json` (created by `add-model`): your extra models, merged over the defaults.
- `openrouter/auto` (key `auto`) is OpenRouter's auto-router; set any role to `auto` to let OpenRouter choose.

## Skills
Prompts live in `kirimaru/skills/*.md`. Edit them to change behavior without touching code.
