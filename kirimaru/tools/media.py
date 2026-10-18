"""Free/cheap tools. Deterministic work happens here so the LLM only sees what it must."""
import json
import re
import shutil
import subprocess
from pathlib import Path

COOKIES_ROOT = Path(__file__).resolve().parents[2] / "output" / "profiles"

_PLATFORM_HOSTS = {
    "youtube": ("youtube.com", "youtu.be"),
    "tiktok": ("tiktok.com",),
    "instagram": ("instagram.com",),
    "twitch": ("twitch.tv",),
}


def _cookies_for(url: str) -> list[str]:
    """Return --cookiefile args when a saved login matches this URL, else empty."""
    for platform, hosts in _PLATFORM_HOSTS.items():
        if any(h in url for h in hosts):
            cf = COOKIES_ROOT / platform / "cookies.txt"
            if cf.exists():
                return ["--cookiefile", str(cf)]
    return []


def ffmpeg_bin() -> str:
    """System ffmpeg if on PATH, otherwise the ffmpeg bundled with imageio-ffmpeg."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def have(bin_name: str) -> bool:
    return shutil.which(bin_name) is not None


def fetch_info(url: str) -> dict:
    """Metadata only (no download). Works for YouTube, Twitch VODs/clips, TikTok, Instagram, and most sites yt-dlp supports."""
    try:
        out = subprocess.run(["yt-dlp", "--dump-single-json", "--no-playlist", "--skip-download",
                              *_cookies_for(url), url],
                             capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        tail = (e.stderr or "").strip().splitlines()
        detail = tail[-1] if tail else "unknown error"
        raise RuntimeError(f"Could not fetch '{url}': {detail}") from e
    info = json.loads(out.stdout)
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "duration": info.get("duration"),
        "uploader": info.get("uploader"),
        "extractor": info.get("extractor"),
        "subtitles": sorted(list((info.get("subtitles") or {}).keys())),
        "auto_captions": sorted(list((info.get("automatic_captions") or {}).keys()))[:20],
    }


def fetch_captions(url: str, workdir: Path, lang: str = "en") -> Path | None:
    """Download captions (manual preferred, auto as fallback). Returns .vtt path or None. Zero LLM cost."""
    workdir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["yt-dlp", "--skip-download", "--write-subs", "--write-auto-subs",
         "--sub-langs", lang, "--sub-format", "vtt", "--no-playlist",
         "-o", str(workdir / "captions.%(ext)s"), *_cookies_for(url), url],
        capture_output=True, text=True,
    )
    matches = sorted(workdir.glob("captions*.vtt"))
    return matches[0] if matches else None


_TS = re.compile(r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s+-->")


def parse_vtt(path: Path) -> list[dict]:
    """Parse VTT to segments, deduping the rolling auto-caption repeats."""
    segments, last_text = [], None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        m = _TS.search(lines[i])
        if m:
            start = _secs(lines[i][:12])
            end = _secs(lines[i].split("-->")[1].strip()[:12])
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(re.sub(r"<[^>]+>", " ", lines[i]).strip())
                i += 1
            text = " ".join(t for t in text_lines if t)
            if text and text != last_text:
                segments.append({"start": start, "end": end, "text": text})
                last_text = text
        i += 1
    return segments


def _secs(ts: str) -> float:
    h, m, rest = ts.strip().split(":")
    s, ms = re.split(r"[.,]", rest, maxsplit=1)
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def chunk_segments(segments: list[dict], window: float = 120.0) -> list[dict]:
    """Group segments into ~window-second chunks. Each chunk is one cheap LLM scoring call."""
    chunks, cur, cur_start = [], [], None
    for seg in segments:
        if cur_start is None:
            cur_start = seg["start"]
        cur.append(seg)
        if seg["end"] - cur_start >= window:
            chunks.append(_make_chunk(cur))
            cur, cur_start = [], None
    if cur:
        chunks.append(_make_chunk(cur))
    return chunks


def _make_chunk(segs: list[dict]) -> dict:
    return {"start": segs[0]["start"], "end": segs[-1]["end"],
            "text": " ".join(s["text"] for s in segs)}


def download_media(url: str, workdir: Path, max_height: int = 720) -> Path:
    """Download a video file (only called when a multimodal model is actually needed)."""
    workdir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["yt-dlp", "--no-playlist", "-f", f"bv*[height<={max_height}]+ba/b[height<={max_height}]",
         "--merge-output-format", "mp4", "-o", str(workdir / "source.%(ext)s"),
         *_cookies_for(url), url],
        check=True,
    )
    return next(workdir.glob("source.*"))


def cut_clip(source: Path, start: float, end: float, out: Path) -> Path:
    """Re-encode the cut with ffmpeg (small, fast preset).

    Uses a fast keyframe seek to just before the cut, then an accurate output
    seek and duration so the clip starts on the exact requested timestamp.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    pre = max(0.0, start - 3.0)
    offset = start - pre
    duration = end - start
    subprocess.run(
        [ffmpeg_bin(), "-y", "-ss", f"{pre:.2f}", "-i", str(source),
         "-ss", f"{offset:.2f}", "-t", f"{duration:.2f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         "-c:a", "aac", "-movflags", "+faststart", str(out)],
        check=True, capture_output=True,
    )
    return out


def burn_title(src: Path, title: str, out: Path, seconds: float = 3.0) -> Path:
    """Overlay the title on the first few seconds of a clip (title card style, top of frame).

    The title is written to a temp text file and passed with textfile=, which avoids
    escaping problems in the ffmpeg filter syntax. Runs with cwd set to the output folder
    so the font path has no drive-letter colon.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    text_file = out.with_suffix(".title.txt")
    text_file.write_text(title, encoding="utf-8")
    font = Path("C:/Windows/Fonts/arial.ttf")
    font_arg = ""
    if font.exists():
        local_font = out.parent / "title_font.ttf"
        if not local_font.exists():
            local_font.write_bytes(font.read_bytes())
        font_arg = "fontfile=title_font.ttf:"
    vf = (f"drawtext={font_arg}textfile={text_file.name}:fontsize=h/18:fontcolor=white:"
          f"borderw=4:bordercolor=black:x=(w-text_w)/2:y=h*0.12:"
          f"enable='lt(t,{seconds})'")
    subprocess.run(
        [ffmpeg_bin(), "-y", "-i", str(src.resolve()), "-vf", vf, "-c:a", "copy",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         "-metadata", f"title={title}", "-movflags", "+faststart", str(out.resolve())],
        check=True, capture_output=True, cwd=str(out.parent.resolve()),
    )
    text_file.unlink(missing_ok=True)
    return out
