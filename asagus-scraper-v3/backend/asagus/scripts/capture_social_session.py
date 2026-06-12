from __future__ import annotations

import argparse
import asyncio
import re
from pathlib import Path

from asagus.config import get_settings
from asagus.models import SocialPlatform


LOGIN_URLS = {
    SocialPlatform.facebook: "https://www.facebook.com/login",
    SocialPlatform.instagram: "https://www.instagram.com/accounts/login/",
}


def safe_label(value: str) -> str:
    label = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip())
    label = label.strip(".-") or "default"
    return label.replace("..", ".")


def default_sessions_dir() -> Path:
    settings = get_settings()
    if settings.social_auth_sessions_dir.strip():
        path = Path(settings.social_auth_sessions_dir).expanduser()
        return path if path.is_absolute() else (Path(__file__).resolve().parents[3] / path).resolve()
    return Path(__file__).resolve().parents[3] / "data" / "social_auth_sessions"


async def capture(platform: SocialPlatform, session_label: str, output: Path | None = None) -> Path:
    from playwright.async_api import async_playwright

    target = output or default_sessions_dir() / safe_label(session_label) / f"{platform.value}.storage_state.json"
    target.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1365, "height": 900})
        page = await context.new_page()
        await page.goto(LOGIN_URLS[platform], wait_until="domcontentloaded")
        await asyncio.to_thread(
            input,
            f"Log in to {platform.value} in the opened browser, then press Enter here to save the session... ",
        )
        await context.storage_state(path=str(target))
        await browser.close()
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture an authorized Facebook/Instagram browser session.")
    parser.add_argument("platform", choices=[platform.value for platform in SocialPlatform])
    parser.add_argument("--session-label", default="default")
    parser.add_argument("--output", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    platform = SocialPlatform(args.platform)
    output = Path(args.output).expanduser() if args.output else None
    saved = asyncio.run(capture(platform, args.session_label, output))
    print(f"Saved {platform.value} storage state: {saved}")


if __name__ == "__main__":
    main()
