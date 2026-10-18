---
name: multimodal-moments
description: Use only when no transcript exists or visuals matter. Find clip moments from raw audio/video.
---
You are given a video or audio file. Find the most clip-worthy moments (15-60 s each) based on
both what is said AND what is shown (reactions, gestures, action, visual gags).

Return ONLY JSON:
{"clips": [{"start": <seconds>, "end": <seconds>, "title": "<text>", "hook": "<text>", "why": "<text>"}]}
