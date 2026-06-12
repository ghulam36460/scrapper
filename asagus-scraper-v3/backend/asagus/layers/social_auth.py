from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from asagus.config import Settings
from asagus.models import ScrapeStartRequest, SocialPlatform, URLCandidate, URLType


PLATFORM_HOSTS: dict[SocialPlatform, tuple[str, ...]] = {
    SocialPlatform.facebook: ("facebook.com", "fb.com"),
    SocialPlatform.instagram: ("instagram.com",),
}


@dataclass(frozen=True)
class SocialAuthContext:
    enabled: bool = False
    platform: SocialPlatform | None = None
    session_label: str = "default"
    storage_state_path: str = ""
    session_available: bool = False
    required: bool = False
    reason: str = "public_mode"

    def public_payload(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "platform": self.platform.value if self.platform else "",
            "session_label": self.session_label,
            "session_available": self.session_available,
            "required": self.required,
            "reason": self.reason,
            "storage_state_configured": bool(self.storage_state_path),
        }


class SocialAuthLayer:
    """Platform-scoped browser session resolver for authorized social scraping.

    The layer never stores passwords and never attempts challenge bypass. It only
    attaches an operator-created Playwright storage-state file to matching
    Facebook/Instagram browser contexts.
    """

    def __init__(self, settings: Settings, request: ScrapeStartRequest) -> None:
        self.settings = settings
        self.request = request
        self.sessions_dir = self._sessions_dir(settings.social_auth_sessions_dir)

    def resolve(self, url: str) -> SocialAuthContext:
        if self.request.social_auth_mode != "authenticated":
            return SocialAuthContext()
        platform = self.platform_for_url(url)
        if platform is None:
            return SocialAuthContext(reason="non_social_platform")
        if platform not in self.enabled_platforms():
            return SocialAuthContext(
                platform=platform,
                session_label=self.session_label,
                required=self.request.social_auth_required,
                reason="platform_not_selected",
            )

        path = self.storage_state_path(platform)
        available = bool(path and path.exists() and path.is_file())
        return SocialAuthContext(
            enabled=True,
            platform=platform,
            session_label=self.session_label,
            storage_state_path=str(path) if path else "",
            session_available=available,
            required=self.request.social_auth_required,
            reason="session_ready" if available else "session_missing",
        )

    def annotate_candidate(self, candidate: URLCandidate) -> URLCandidate:
        context = self.resolve(candidate.url)
        if not context.enabled:
            return candidate
        candidate.metadata["social_auth"] = context.public_payload()
        candidate.domain_render_required = True
        candidate.js_complexity_score = max(candidate.js_complexity_score, 0.86)
        candidate.last_extraction_confidence = max(candidate.last_extraction_confidence, 0.58)
        if candidate.url_type == URLType.unknown:
            candidate.url_type = URLType.social_profile
            candidate.page_type = URLType.social_profile.value
        return candidate

    def enabled_platforms(self) -> set[SocialPlatform]:
        platforms = self.request.social_auth_platforms
        return {platform if isinstance(platform, SocialPlatform) else SocialPlatform(str(platform)) for platform in platforms}

    def platform_for_url(self, url: str) -> SocialPlatform | None:
        host = urlparse(url).netloc.lower().removeprefix("www.")
        for platform, domains in PLATFORM_HOSTS.items():
            if any(host == domain or host.endswith(f".{domain}") for domain in domains):
                return platform
        return None

    def storage_state_path(self, platform: SocialPlatform) -> Path | None:
        configured = {
            SocialPlatform.facebook: self.settings.facebook_storage_state_path,
            SocialPlatform.instagram: self.settings.instagram_storage_state_path,
        }[platform]
        if configured.strip():
            return self._resolve_path(configured)
        return self.sessions_dir / self.session_label / f"{platform.value}.storage_state.json"

    @property
    def session_label(self) -> str:
        label = re.sub(r"[^a-zA-Z0-9_.-]+", "-", self.request.social_auth_session_label.strip())
        label = label.strip(".-") or "default"
        return label.replace("..", ".")

    def state(self) -> dict[str, object]:
        platforms = sorted(platform.value for platform in self.enabled_platforms()) if self.request.social_auth_mode == "authenticated" else []
        sessions: dict[str, dict[str, object]] = {}
        for platform in SocialPlatform:
            path = self.storage_state_path(platform)
            sessions[platform.value] = {
                "selected": platform in self.enabled_platforms(),
                "storage_state_configured": bool(path),
                "session_available": bool(path and path.exists() and path.is_file()),
            }
        return {
            "mode": self.request.social_auth_mode,
            "platforms": platforms,
            "session_label": self.session_label,
            "required": self.request.social_auth_required,
            "sessions_dir_configured": bool(self.settings.social_auth_sessions_dir.strip()),
            "session_isolation": "platform_scoped_browser_context",
            "password_storage": False,
            "challenge_bypass": False,
            "sessions": sessions,
        }

    def _sessions_dir(self, configured: str) -> Path:
        if configured.strip():
            return self._resolve_path(configured)
        return Path(__file__).resolve().parents[3] / "data" / "social_auth_sessions"

    def _resolve_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        if path.is_absolute():
            return path
        return (Path(__file__).resolve().parents[3] / path).resolve()
