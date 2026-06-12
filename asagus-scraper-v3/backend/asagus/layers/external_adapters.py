from __future__ import annotations

import importlib
import importlib.util
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from asagus.models import FetchMode, FetchResult, ProxyEndpoint, URLCandidate


CONTACT_HINT_RE = re.compile(r"(contact|about|team|support|help|location|branch|impressum)", re.I)
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+|00)?\d[\d\s().-]{7,}\d")
SCRIPT_NOISE_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.I | re.S)


@dataclass(frozen=True)
class AdapterStatus:
    key: str
    name: str
    available: bool
    status: str
    role: str
    package: str = ""
    source: str = ""
    license: str = ""
    detail: str = ""
    backends: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "available": self.available,
            "status": self.status,
            "role": self.role,
            "package": self.package,
            "source": self.source,
            "license": self.license,
            "detail": self.detail,
            "backends": self.backends,
        }


@dataclass(frozen=True)
class PlatformChannel:
    key: str
    name: str
    domains: tuple[str, ...]
    backends: tuple[str, ...] = ()
    tier: int = 0

    def can_handle(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return any(domain in host for domain in self.domains)

    def health(self) -> dict[str, object]:
        backend_status = {backend: _backend_available(backend) for backend in self.backends}
        available = all(backend_status.values()) if backend_status else True
        return {
            "name": self.name,
            "available": available,
            "status": "ok" if available else "off",
            "tier": self.tier,
            "backends": list(self.backends),
            "backend_status": backend_status,
        }


PLATFORM_CHANNELS: tuple[PlatformChannel, ...] = (
    PlatformChannel("web", "General web", ("",), tier=0),
    PlatformChannel("rss", "RSS/Atom feeds", ("/feed", "/rss", ".xml", "atom"), ("feedparser",), tier=0),
    PlatformChannel("youtube", "YouTube pages and subtitles", ("youtube.com", "youtu.be"), ("yt-dlp",), tier=0),
    PlatformChannel("github", "GitHub repositories and profiles", ("github.com",), ("gh",), tier=1),
    PlatformChannel("reddit", "Reddit public pages", ("reddit.com",), tier=1),
    PlatformChannel("linkedin", "LinkedIn public profiles", ("linkedin.com",), tier=2),
    PlatformChannel("twitter", "X/Twitter public profiles", ("x.com", "twitter.com"), tier=2),
)


def external_adapter_state() -> dict[str, object]:
    adapters = [
        _package_status(
            "scrapy",
            "Scrapy Selector Adapter",
            "Scrapy/parsel-style CSS and XPath parsing inside ASAGUS extraction",
            "BSD-3-Clause",
            local_path="scrapy-master",
        ),
        _package_status(
            "parsel",
            "Parsel Selector Fallback",
            "Selector engine shared by Scrapy for local HTML parsing",
            "BSD",
        ),
        _package_status(
            "scrapling",
            "Scrapling Parser/Fetch Adapter",
            "Adaptive parser and optional static fetch fallback",
            "BSD-3-Clause",
            local_path="Scrapling-main",
        ),
        _package_status(
            "scrapegraphai",
            "ScrapeGraphAI Adapter",
            "Optional LLM graph extraction path when installed/configured",
            "MIT",
            local_path="Scrapegraph-ai-main",
        ),
        _package_status(
            "firecrawl",
            "Firecrawl API Adapter",
            "Optional hosted/API markdown scrape/search adapter",
            "AGPL-3.0 upstream core; SDKs may differ",
            local_path="firecrawl-main",
            configured=bool(os.getenv("FIRECRAWL_API_KEY")),
        ),
        _package_status(
            "agent_reach",
            "Agent Reach Channel Doctor",
            "External channel availability checks inspired by Agent Reach",
            "MIT",
            local_path="Agent-Reach-main",
        ),
    ]
    packages = {
        name: {
            "available": importlib.util.find_spec(name) is not None,
            "source": _module_source(name),
        }
        for name in ("bs4", "lxml", "ddgs", "playwright", "feedparser", "yt_dlp")
    }
    return {
        "adapters": {item.key: item.as_dict() for item in adapters},
        "packages": packages,
        "platform_channels": platform_channel_doctor(),
        "download_root": str(_download_root()),
        "integration_style": "native_glue_and_optional_adapters",
    }


def platform_channel_doctor() -> dict[str, dict[str, object]]:
    channels: dict[str, dict[str, object]] = {}
    for channel in PLATFORM_CHANNELS:
        if channel.key == "web":
            channels[channel.key] = channel.health()
            continue
        channels[channel.key] = channel.health()
    return channels


def platform_for_url(url: str) -> str:
    lower = (url or "").lower()
    for channel in PLATFORM_CHANNELS:
        if channel.key == "rss" and any(token in lower for token in channel.domains):
            return channel.key
        if channel.key != "web" and channel.can_handle(url):
            return channel.key
    return "web"


class ScrapySelectorAdapter:
    """Small Scrapy/parsel-powered extractor used as an ASAGUS extraction helper."""

    def __init__(self) -> None:
        self.selector_cls: Any | None = None
        self.engine = ""
        try:
            module = importlib.import_module("scrapy")
            self.selector_cls = getattr(module, "Selector")
            self.engine = "scrapy.Selector"
        except Exception:
            try:
                module = importlib.import_module("parsel")
                self.selector_cls = getattr(module, "Selector")
                self.engine = "parsel.Selector"
            except Exception:
                self.selector_cls = None

    @property
    def available(self) -> bool:
        return self.selector_cls is not None

    def extract(self, html: str, url: str) -> dict[str, object]:
        if not self.selector_cls or not html:
            return {}
        try:
            selector = self.selector_cls(text=html)
        except Exception:
            return {}

        title = _first_selector_value(
            selector,
            [
                "meta[property='og:title']::attr(content)",
                "meta[name='twitter:title']::attr(content)",
                "h1::text",
                "title::text",
                "[itemprop='name']::attr(content)",
                "[itemprop='name']::text",
            ],
        )
        email = _first_selector_value(
            selector,
            [
                "a[href^='mailto:']::attr(href)",
                "[itemprop='email']::attr(content)",
                "[itemprop='email']::text",
            ],
        )
        phone = _first_selector_value(
            selector,
            [
                "a[href^='tel:']::attr(href)",
                "[itemprop='telephone']::attr(content)",
                "[itemprop='telephone']::text",
                "[itemprop='phone']::attr(content)",
                "[itemprop='phone']::text",
            ],
        )
        address = _first_selector_value(
            selector,
            [
                "address::text",
                "[itemprop='address']::attr(content)",
                "[itemprop='address']::text",
                ".address::text",
                ".location::text",
            ],
        )
        website_url = _first_selector_value(
            selector,
            [
                "link[rel='canonical']::attr(href)",
                "meta[property='og:url']::attr(content)",
            ],
        )
        category = _first_selector_value(
            selector,
            [
                "[itemprop='category']::attr(content)",
                "[itemprop='category']::text",
                "meta[property='business:category']::attr(content)",
            ],
        )
        contact_links = [
            urljoin(url, href)
            for href in selector.css("a::attr(href)").getall()
            if href and CONTACT_HINT_RE.search(href)
        ][:12]
        visible_text = _visible_text(html)
        fallback_email = next(iter(EMAIL_RE.findall(visible_text)), "")
        fallback_phone = next(iter(PHONE_RE.findall(visible_text)), "")
        fields: dict[str, object] = {
            "adapter": self.engine,
            "title": _clean(title),
            "email": _clean(email).removeprefix("mailto:"),
            "phone": _clean(phone).removeprefix("tel:"),
            "address": _clean(address),
            "website_url": urljoin(url, website_url) if website_url else "",
            "category": _clean(category),
            "contact_links": contact_links,
            "link_count": len(selector.css("a::attr(href)").getall()),
        }
        if not fields["email"] and fallback_email:
            fields["email"] = fallback_email
        if not fields["phone"] and fallback_phone:
            fields["phone"] = fallback_phone
        return {key: value for key, value in fields.items() if _has_value(value)}


class ScraplingParserAdapter:
    """Scrapling parser bridge for adaptive text/selector signals."""

    def __init__(self) -> None:
        self.parser_cls: Any | None = None
        self.engine = ""
        try:
            module = importlib.import_module("scrapling.parser")
            self.parser_cls = getattr(module, "Selector", None) or getattr(module, "Adaptor", None)
            self.engine = f"scrapling.{getattr(self.parser_cls, '__name__', 'parser')}" if self.parser_cls else ""
        except Exception:
            self.parser_cls = None

    @property
    def available(self) -> bool:
        return self.parser_cls is not None

    def extract(self, html: str, url: str) -> dict[str, object]:
        if not self.parser_cls or not html:
            return {}
        try:
            parser = self.parser_cls(html, url=url)
        except Exception:
            return {}
        title = self._css_text(parser, "title") or self._css_text(parser, "h1")
        item_name = self._css_text(parser, "[itemprop='name']")
        item_phone = self._css_text(parser, "[itemprop='telephone']") or self._css_text(parser, "[itemprop='phone']")
        item_email = self._css_text(parser, "[itemprop='email']")
        item_address = self._css_text(parser, "[itemprop='address']") or self._css_text(parser, "address")
        text = self._all_text(parser)
        fields: dict[str, object] = {
            "adapter": self.engine,
            "title": _clean(item_name or title),
            "email": _clean(item_email) or next(iter(EMAIL_RE.findall(text)), ""),
            "phone": _clean(item_phone) or next(iter(PHONE_RE.findall(text)), ""),
            "address": _clean(item_address),
            "text_length": len(text),
        }
        return {key: value for key, value in fields.items() if _has_value(value)}

    def _css_text(self, parser: Any, css: str) -> str:
        try:
            if hasattr(parser, "css_first"):
                node = parser.css_first(css)
            else:
                nodes = parser.css(css)
                node = nodes[0] if nodes else None
        except Exception:
            return ""
        if node is None:
            return ""
        value = getattr(node, "text", "")
        if value:
            return str(value)
        get = getattr(node, "get", None)
        if callable(get):
            try:
                return str(get())
            except Exception:
                return ""
        return str(node)

    def _all_text(self, parser: Any) -> str:
        for name in ("get_all_text", "text"):
            value = getattr(parser, name, None)
            try:
                if callable(value):
                    return str(value())
                if value:
                    return str(value)
            except Exception:
                continue
        return ""


class ScraplingFetchAdapter:
    """Optional static fetch fallback using Scrapling's AsyncFetcher when installed."""

    def __init__(self) -> None:
        self.available = importlib.util.find_spec("scrapling") is not None

    async def fetch(self, candidate: URLCandidate, started: float, proxy: ProxyEndpoint) -> FetchResult:
        if not self.available:
            return FetchResult(
                url=candidate.url,
                fetch_mode=FetchMode.static,
                proxy_used=proxy.id,
                render_time_ms=int((time.perf_counter() - started) * 1000),
                error="scrapling_not_installed",
            )
        try:
            from scrapling.fetchers import AsyncFetcher  # type: ignore

            response = await AsyncFetcher.get(
                candidate.url,
                follow_redirects=True,
                timeout=20,
                proxy=proxy.endpoint or None,
                retries=1,
            )
            html = str(getattr(response, "html_content", "") or getattr(response, "text", "") or "")
            status = int(getattr(response, "status", 0) or 0)
            headers = getattr(response, "headers", {}) or {}
            final_url = str(getattr(response, "url", "") or candidate.url)
            return FetchResult(
                url=candidate.url,
                status_code=status,
                final_url=final_url,
                content_type=str(headers.get("content-type", "")) if isinstance(headers, dict) else "",
                html=html,
                markdown=html,
                fetch_mode=FetchMode.static,
                proxy_used=proxy.id,
                render_time_ms=int((time.perf_counter() - started) * 1000),
                error="scrapling_static_fetch",
            )
        except Exception as exc:
            return FetchResult(
                url=candidate.url,
                fetch_mode=FetchMode.static,
                proxy_used=proxy.id,
                render_time_ms=int((time.perf_counter() - started) * 1000),
                error=f"scrapling_failed: {exc}",
            )


def _package_status(
    package: str,
    name: str,
    role: str,
    license_name: str,
    local_path: str = "",
    configured: bool | None = None,
) -> AdapterStatus:
    available = importlib.util.find_spec(package) is not None
    local_source = _download_root() / local_path if local_path else None
    source = _module_source(package) if available else str(local_source) if local_source and local_source.exists() else ""
    if available and configured is False:
        status = "needs_configuration"
    elif available:
        status = "ok"
    elif local_source and local_source.exists():
        status = "source_available_not_installed"
    else:
        status = "off"
    detail = "installed" if available else "downloaded source found" if source else "not installed"
    if configured is False:
        detail = f"{detail}; missing API key or runtime configuration"
    return AdapterStatus(
        key=package,
        name=name,
        available=available,
        status=status,
        role=role,
        package=package,
        source=source,
        license=license_name,
        detail=detail,
    )


def _backend_available(backend: str) -> bool:
    if backend in {"yt-dlp", "gh"}:
        return shutil.which(backend) is not None
    module_name = backend.replace("-", "_")
    return importlib.util.find_spec(module_name) is not None


def _module_source(package: str) -> str:
    try:
        spec = importlib.util.find_spec(package)
        return str(spec.origin or "") if spec else ""
    except Exception:
        return ""


def _download_root() -> Path:
    configured = os.getenv("ASAGUS_EXTERNAL_TOOLS_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path(__file__).resolve().parents[4] / "Download"


def _first_selector_value(selector: Any, selectors: list[str]) -> str:
    for expression in selectors:
        try:
            value = selector.css(expression).get()
        except Exception:
            value = None
        if value:
            return str(value)
    return ""


def _visible_text(html: str) -> str:
    text = SCRIPT_NOISE_RE.sub(" ", html or "")
    return unescape(re.sub(r"<[^>]+>", " ", text))


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(value or ""))).strip()


def _has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True
