"""
ASAGUS Adapter for ScrapeGraph-AI — LLM-powered extraction worker.

ScrapeGraph-AI needs an LLM. To honor the "no required API key" rule, this
worker runs ONLY when an LLM is already configured for ASAGUS (any of:
OPENAI_API_KEY, ANTHROPIC_API_KEY, LLM_API_KEY, or a local OLLAMA endpoint via
OLLAMA_BASE_URL). If neither the package nor an LLM is available, it SKIPS
gracefully instead of failing the job.

When active, it discovers seed URLs (DuckDuckGo, no key) and runs
SmartScraperGraph on each to extract business contact data, then writes a
unified CSV (<tool_id>.csv) for the ASAGUS csv_merger.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))
from unified_tool_adapter import UnifiedToolAdapter, get_llm_config  # noqa: E402


_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?:\+\d{1,4}[\s().-]?)?(?:\(?\d{2,4}\)?[\s().-]?){2,5}\d{2,4}")
_WA_RE = re.compile(r"(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\+?\d[\d\s().-]{6,})", re.I)


def _clean_phone(raw: str) -> str:
    cleaned = re.sub(r"\s+", " ", raw).strip(" .,-()")
    # Reject ISO date-like patterns (e.g. 2021-08-16, 2013/08/06).
    if re.fullmatch(r"(?:19|20)\d{2}[-/.]\d{1,2}[-/.]\d{1,2}", cleaned):
        return ""
    digits = re.sub(r"\D", "", raw)
    if 7 <= len(digits) <= 15 and len(set(digits)) >= 3 and not digits.startswith(("000", "123456")):
        if "+" in raw or any(c in raw for c in "()- ") or len(digits) >= 9:
            return cleaned
    return ""


# Mode -> number of URLs to run the (relatively expensive) LLM graph on.
_MODE_URL_BUDGET: dict[str, int] = {
    "fast": 3, "focused": 3, "balanced": 5,
    "deep": 8, "research": 8, "comprehensive": 10,
    "deep_agent": 12, "adaptive": 12, "parallel": 12, "max": 15,
}

_EXTRACT_PROMPT = (
    "Extract the business contact details as JSON with keys: "
    "name, phone, whatsapp, email, address, city, website_url, "
    "facebook_url, instagram_url, category. Use empty string for unknown fields."
)

_SKIP_DOMAINS = (
    "google.", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "youtube.com", "linkedin.com", "tripadvisor.", "yelp.", "wikipedia.org",
    "amazon.", "ebay.", "duckduckgo.com",
)


def _resolve_llm_graph_config() -> dict[str, Any] | None:
    """Build a scrapegraphai graph_config from available LLM credentials.

    Returns None when no usable LLM is configured (so the worker can skip).
    """
    cfg = get_llm_config()
    api_key = cfg.get("api_key") or ""
    provider = (cfg.get("provider") or "").lower()
    model = cfg.get("model") or ""

    # 1. Local Ollama (no API key needed).
    ollama_base = os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_HOST")
    if (provider in {"ollama", "local"} or (not api_key and ollama_base)):
        base = ollama_base or "http://localhost:11434"
        return {
            "llm": {
                "model": f"ollama/{model or 'llama3'}",
                "base_url": base,
                "temperature": 0,
            },
            "verbose": False,
            "headless": True,
        }

    if not api_key:
        return None

    # 2. OpenAI-compatible / Anthropic via key.
    if "anthropic" in provider or os.environ.get("ANTHROPIC_API_KEY"):
        return {
            "llm": {
                "api_key": os.environ.get("ANTHROPIC_API_KEY", api_key),
                "model": model or "anthropic/claude-3-haiku-20240307",
                "temperature": 0,
            },
            "verbose": False,
            "headless": True,
        }
    return {
        "llm": {
            "api_key": api_key,
            "model": model or "openai/gpt-4o-mini",
            "temperature": 0,
        },
        "verbose": False,
        "headless": True,
    }


def _is_business_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return bool(host) and not any(s in host for s in _SKIP_DOMAINS)


def _ddg_seed_urls(query: str, location: str, max_results: int) -> list[str]:
    """Resilient multi-engine seed discovery (DDG -> Bing), no API key.

    Parallel workers can be rate-limited by a single engine, so this rotates a
    randomized User-Agent, retries with jitter, and falls back to Bing.
    """
    import random
    import time as _time
    from urllib.parse import parse_qs, quote_plus, unquote

    try:
        import requests
        from bs4 import BeautifulSoup
    except Exception:
        return []

    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    ]
    q = f"{query} {location}".strip()
    seen: set[str] = set()
    out: list[str] = []

    def _collect(hrefs: list[str]) -> None:
        for href in hrefs:
            if href.startswith("//duckduckgo.com/l/?uddg="):
                href = unquote(parse_qs(urlparse(href).query).get("uddg", [""])[0])
            if not href.startswith("http") or not _is_business_url(href):
                continue
            d = urlparse(href).netloc.lower()
            if d and d not in seen:
                seen.add(d)
                out.append(href.split("#")[0])

    for attempt in range(3):
        headers = {"User-Agent": random.choice(user_agents)}
        try:
            resp = requests.post(
                "https://html.duckduckgo.com/html/",
                data={"q": q}, headers=headers, timeout=20,
            )
            if resp.status_code < 400:
                soup = BeautifulSoup(resp.text, "html.parser")
                _collect([a.get("href", "") for a in soup.select(".result__title a, a.result__a")])
        except Exception:
            pass
        if len(out) >= max_results:
            return out[:max_results]
        _time.sleep(0.6 + random.random() * 1.4)

    # Fallback: Bing HTML.
    try:
        headers = {"User-Agent": random.choice(user_agents)}
        resp = requests.get(
            f"https://www.bing.com/search?q={quote_plus(q)}&count=30",
            headers=headers, timeout=20,
        )
        if resp.status_code < 400:
            soup = BeautifulSoup(resp.text, "html.parser")
            _collect([a.get("href", "") for a in soup.select("li.b_algo h2 a, h2 a")])
    except Exception:
        pass
    return out[:max_results]


def _fetch_html(url: str) -> str | None:
    """Fetch HTML for a URL (no API key). Plain HTTP first, then a rendered
    Playwright fallback for JS-heavy pages, mirroring ScrapeGraph-AI's browser
    rendering without requiring an LLM."""
    try:
        import requests

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code < 400 and len(resp.text) > 800:
            return resp.text
    except Exception:
        pass

    # Rendered fallback for JS-driven sites.
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    )
                )
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                return page.content()
            finally:
                browser.close()
    except Exception:
        return None


def _extract_record_no_llm(html: str, url: str) -> dict[str, Any] | None:
    """Regex/heuristic extraction of business contact data (no LLM required)."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        title = (soup.title.string.strip() if soup.title and soup.title.string else "")
        links = [a.get("href", "") for a in soup.find_all("a", href=True)]
    except Exception:
        text = html
        title = ""
        links = re.findall(r'href=["\'](https?://[^"\']+)["\']', html)

    host = urlparse(url).netloc.lower().removeprefix("www.")
    name = title.split("|")[0].split("-")[0].strip() or host.split(".")[0].replace("-", " ").title()

    emails = [e.lower() for e in _EMAIL_RE.findall(text)
              if not e.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
              and not any(b in e.lower() for b in ("example.", "sentry.", "wixpress.", "schema.org"))]
    phones = [p for p in (_clean_phone(m.group(0)) for m in _PHONE_RE.finditer(text)) if p]
    wa = [m.group(1).strip() for m in _WA_RE.finditer(html)]

    def _social(domain: str) -> str:
        for href in links:
            if domain in href.lower():
                return href.split("?")[0]
        return ""

    rec = {
        "name": name,
        "email": emails[0] if emails else "",
        "phone": phones[0] if phones else "",
        "whatsapp": wa[0] if wa else "",
        "website_url": url,
        "source_url": url,
        "facebook_url": _social("facebook.com"),
        "instagram_url": _social("instagram.com"),
        "linkedin_url": _social("linkedin.com"),
    }
    if not any(rec.get(f) for f in ("phone", "email", "whatsapp")):
        return None
    return rec


class ScrapeGraphAIAdapter(UnifiedToolAdapter):
    """Mode-aware extraction worker.

    Uses ScrapeGraph-AI's LLM graph when an LLM is configured (local Ollama or
    an API key); otherwise falls back to a no-LLM regex/heuristic extractor so
    the worker still produces real records without requiring any API key.
    """

    def run(self) -> dict[str, Any]:
        context = self.get_job_context()

        try:
            from scrapegraphai.graphs import SmartScraperGraph  # type: ignore
            _pkg_ok = True
        except Exception:
            SmartScraperGraph = None  # type: ignore
            _pkg_ok = False

        graph_config = _resolve_llm_graph_config() if _pkg_ok else None
        llm_mode = graph_config is not None

        extraction_mode = "llm" if llm_mode else "heuristic_no_llm"

        if not self.real_run:
            data = {
                "tool_id": self.tool_id,
                "status": "prepared",
                "message": f"ScrapeGraph-AI ready ({extraction_mode}); dry run.",
                "mode": self.mode,
                "extraction_mode": extraction_mode,
                "scrapegraphai_installed": _pkg_ok,
                "job_context": context,
            }
            self.save_metadata_json(data)
            return data

        url_budget = min(_MODE_URL_BUDGET.get(self.mode, 5), max(self.limit, 3))
        seeds = _ddg_seed_urls(self.query, self.location, url_budget)
        if not seeds:
            data = {
                "tool_id": self.tool_id,
                "status": "no_seeds",
                "message": "No seed URLs discovered.",
                "extraction_mode": extraction_mode,
                "job_context": context,
            }
            self.save_metadata_json(data)
            return data

        records: list[dict[str, Any]] = []
        errors: list[str] = []
        for url in seeds:
            try:
                if llm_mode and SmartScraperGraph is not None:
                    graph = SmartScraperGraph(prompt=_EXTRACT_PROMPT, source=url, config=graph_config)
                    result = graph.run()
                    rec = self._normalize_llm_result(result, url)
                else:
                    html = _fetch_html(url)
                    rec = _extract_record_no_llm(html, url) if html else None
                if rec:
                    rec["source_tool"] = self.tool_id
                    records.append(rec)
            except Exception as exc:
                errors.append(f"{url}: {str(exc)[:160]}")
                continue

        if records:
            self.save_records_csv(records)

        data = {
            "tool_id": self.tool_id,
            "status": "completed" if records else "no_records",
            "mode": self.mode,
            "extraction_mode": extraction_mode,
            "scrapegraphai_installed": _pkg_ok,
            "urls_processed": len(seeds),
            "records": len(records),
            "errors": errors[:10],
            "output_csv": str(self.csv_path) if records else "",
            "job_context": context,
        }
        self.save_metadata_json(data)
        return data

    @staticmethod
    def _normalize_llm_result(result: Any, url: str) -> dict[str, Any] | None:
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except Exception:
                return None
        if not isinstance(result, dict):
            return None
        # Some graphs nest under a key; flatten the first dict value if so.
        if result and all(isinstance(v, (dict, list)) for v in result.values()):
            for v in result.values():
                if isinstance(v, dict):
                    result = v
                    break
        rec = {k: ("" if v is None else str(v)) for k, v in result.items() if not isinstance(v, (dict, list))}
        rec.setdefault("source_url", url)
        if not any(rec.get(f) for f in ("phone", "email", "whatsapp", "name")):
            return None
        return rec


def main() -> None:
    print(json.dumps(ScrapeGraphAIAdapter().run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
