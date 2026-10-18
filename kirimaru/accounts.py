"""Account connections via a persistent, user-logged-in browser profile per platform.

Flow: `python -m kirimaru connect youtube` opens a visible browser on that platform's login page.
You log in yourself (KirimaruAI never sees or stores your password). The session cookies stay in
output/profiles/<platform>, so later runs reuse the login. `disconnect` deletes that profile.
"""
import shutil
from pathlib import Path

PROFILES_ROOT = Path(__file__).resolve().parents[1] / "output" / "profiles"

PLATFORMS = {
    "youtube": "https://accounts.google.com/ServiceLogin?service=youtube&continue=https://studio.youtube.com",
    "tiktok": "https://www.tiktok.com/login",
    "instagram": "https://www.instagram.com/accounts/login/",
    "twitch": "https://www.twitch.tv/login",
}


def profile_dir(platform: str) -> Path:
    if platform not in PLATFORMS:
        raise ValueError(f"Unknown platform {platform!r}. Options: {list(PLATFORMS)}")
    return PROFILES_ROOT / platform


def _export_cookies(ctx, platform: str):
    """Dump the logged-in browser cookies to a Netscape cookies.txt that yt-dlp can reuse."""
    cookies = ctx.cookies()
    if not cookies:
        return None
    out = profile_dir(platform) / "cookies.txt"
    lines = ["# Netscape HTTP Cookie File"]
    for c in cookies:
        domain = c.get("domain") or ""
        include = "TRUE" if domain.startswith(".") else "FALSE"
        secure = "TRUE" if c.get("secure") else "FALSE"
        expires = int(c.get("expires") or 0)
        lines.append("\t".join([
            domain, include, c.get("path") or "/", secure,
            str(expires), c.get("name") or "", c.get("value") or "",
        ]))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def connect(platform: str) -> None:
    """Open a visible browser for manual login, then export cookies for yt-dlp reuse."""
    from playwright.sync_api import sync_playwright
    path = profile_dir(platform)
    path.mkdir(parents=True, exist_ok=True)
    print(f"Log in to {platform} in the window that opens.")
    print("When you are logged in, press Enter in this terminal to finish.")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(path), headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(PLATFORMS[platform])
        input()
        cookies_path = _export_cookies(ctx, platform)
        ctx.close()
    extra = f" Exported cookies to {cookies_path.name}." if cookies_path else ""
    print(f"Saved session for {platform}.{extra}")


def status() -> dict:
    return {p: profile_dir(p).exists() and any(profile_dir(p).iterdir()) for p in PLATFORMS}


def disconnect(platform: str) -> None:
    shutil.rmtree(profile_dir(platform), ignore_errors=True)
