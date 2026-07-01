"""
ASAGUS Adapter for Scrapy — real autonomous crawling worker.

Given the ASAGUS job query + location, this worker:
  1. Discovers seed business URLs via DuckDuckGo HTML search (no API key).
  2. Crawls them with a Scrapy spider (depth + page budget scale with the
     main-scraper mode), extracting name / phone / email / whatsapp / socials.
  3. Writes a unified CSV (<tool_id>.csv) for the ASAGUS csv_merger.

Mode -> crawl budget:
    fast / focused / balanced        -> shallow, few pages
    deep / research / comprehensive  -> medium depth
    deep_agent / adaptive / parallel -> deeper
    max                              -> deepest, most pages

This runs as its own subprocess (launched by the ASAGUS backend), so using
Scrapy's CrawlerProcess in the main thread is safe.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))
from unified_tool_adapter import UnifiedToolAdapter  # noqa: E402


# Mode -> (max_seed_urls, max_pages_total, depth_limit, pages_per_domain)
_MODE_BUDGET: dict[str, tuple[int, int, int, int]] = {
    "fast": (10, 40, 1, 3),
    "focused": (10, 40, 1, 3),
    "balanced": (15, 80, 1, 4),
    "deep": (20, 200, 2, 8),
    "research": (20, 200, 2, 8),
    "comprehensive": (25, 280, 2, 10),
    "deep_agent": (30, 400, 3, 12),
    "adaptive": (30, 400, 3, 12),
    "parallel": (30, 400, 3, 12),
    "max": (40, 600, 3, 15),
}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+|00)?\d[\d\s().-]{7,}\d")
WA_RE = re.compile(r"(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\+?\d{8,16})", re.I)
CONTACT_HINT_RE = re.compile(r"(contact|about|team|support|reach|location|impressum)", re.I)
SOCIAL_DOMAINS = {
    "facebook_url": ("facebook.com", "fb.com"),
    "instagram_url": ("instagram.com",),
    "twitter_url": ("x.com", "twitter.com"),
    "linkedin_url": ("linkedin.com",),
}

_SKIP_DOMAINS = (
    "google.", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "youtube.com", "linkedin.com", "tripadvisor.", "yelp.", "wikipedia.org",
    "amazon.", "ebay.", "duckduckgo.com",
)


def _is_business_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    if not host:
        return False
    return not any(skip in host for skip in _SKIP_DOMAINS)


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
    term = f"{query} {location}".strip()
    seen: set[str] = set()
    unique: list[str] = []

    def _collect(hrefs: list[str]) -> None:
        for href in hrefs:
            if href.startswith("//duckduckgo.com/l/?uddg="):
                href = unquote(parse_qs(urlparse(href).query).get("uddg", [""])[0])
            if not href.startswith("http") or not _is_business_url(href):
                continue
            dom = urlparse(href).netloc.lower()
            if dom and dom not in seen:
                seen.add(dom)
                unique.append(href.split("#")[0])

    for _attempt in range(3):
        headers = {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            resp = requests.post(
                "https://html.duckduckgo.com/html/",
                data={"q": term}, headers=headers, timeout=20,
            )
            if resp.status_code < 400:
                soup = BeautifulSoup(resp.text, "html.parser")
                _collect([a.get("href", "") for a in soup.select(".result__title a, a.result__a")])
        except Exception:
            pass
        if len(unique) >= max_results:
            return unique[:max_results]
        _time.sleep(0.6 + random.random() * 1.4)

    try:
        headers = {"User-Agent": random.choice(user_agents)}
        resp = requests.get(
            f"https://www.bing.com/search?q={quote_plus(term)}&count=30",
            headers=headers, timeout=20,
        )
        if resp.status_code < 400:
            soup = BeautifulSoup(resp.text, "html.parser")
            _collect([a.get("href", "") for a in soup.select("li.b_algo h2 a, h2 a")])
    except Exception:
        pass
    return unique[:max_results]


def _is_social(host: str) -> bool:
    host = host.lower()
    return any(d in host for doms in SOCIAL_DOMAINS.values() for d in doms)


def _extract_record(response) -> dict[str, Any] | None:
    try:
        text = " ".join(response.css("body *::text").getall())
    except Exception:
        text = getattr(response, "text", "")
    html = getattr(response, "text", "")

    name = (response.css("meta[property='og:title']::attr(content)").get()
            or response.css("title::text").get() or "").strip()
    name = re.sub(r"\s*[|\-–—].*$", "", name).strip()[:120]

    email = next(iter(EMAIL_RE.findall(text)), "")
    phone = ""
    for cand in PHONE_RE.findall(text):
        digits = re.sub(r"\D", "", cand)
        if 8 <= len(digits) <= 16:
            phone = cand.strip()
            break
    wa = WA_RE.search(html)
    whatsapp = ""
    if wa:
        whatsapp = "+" + re.sub(r"\D", "", wa.group(1))

    socials: dict[str, str] = {}
    for href in response.css("a::attr(href)").getall():
        low = href.lower()
        for field, doms in SOCIAL_DOMAINS.items():
            if field not in socials and any(d in low for d in doms):
                if not any(t in low for t in ("/share", "/sharer", "/intent", "/plugins")):
                    socials[field] = href.split("#")[0]

    if not (email or phone or whatsapp or socials):
        return None

    parsed = urlparse(response.url)
    website = f"{parsed.scheme}://{parsed.netloc}" if not _is_social(parsed.netloc) else ""
    return {
        "name": name,
        "phone": phone,
        "email": email,
        "whatsapp": whatsapp,
        "website_url": website,
        "source_url": response.url,
        **socials,
    }


class ScrapyWorkerAdapter(UnifiedToolAdapter):
    """Real Scrapy crawling worker, mode-aware."""

    def _budget(self) -> tuple[int, int, int, int]:
        return _MODE_BUDGET.get(self.mode, _MODE_BUDGET["balanced"])

    def run(self) -> dict[str, Any]:
        context = self.get_job_context()
        try:
            import scrapy  # noqa: F401
        except ImportError:
            data = {
                "tool_id": self.tool_id,
                "status": "not_installed",
                "error": "Scrapy package not found",
                "install_command": "pip install scrapy",
                "job_context": context,
            }
            self.save_metadata_json(data)
            return data

        if not self.real_run:
            data = {
                "tool_id": self.tool_id,
                "status": "prepared",
                "message": "Scrapy worker ready; real run disabled (dry run).",
                "mode": self.mode,
                "job_context": context,
            }
            self.save_metadata_json(data)
            return data

        max_seeds, max_pages, depth_limit, per_domain = self._budget()
        max_seeds = min(max_seeds, max(self.limit, 5))
        seeds = _ddg_seed_urls(self.query, self.location, max_seeds)
        if not seeds:
            data = {
                "tool_id": self.tool_id,
                "status": "no_seeds",
                "message": "No seed URLs discovered for query/location.",
                "mode": self.mode,
                "job_context": context,
            }
            self.save_metadata_json(data)
            return data

        try:
            records = self._crawl(seeds, max_pages, depth_limit, per_domain)
        except Exception as exc:
            data = {
                "tool_id": self.tool_id,
                "status": "failed",
                "error": str(exc)[:500],
                "mode": self.mode,
                "job_context": context,
            }
            self.save_metadata_json(data)
            return data

        for row in records:
            row.setdefault("source_tool", self.tool_id)
        self.save_records_csv(records)

        data = {
            "tool_id": self.tool_id,
            "status": "completed",
            "mode": self.mode,
            "seed_urls": len(seeds),
            "records": len(records),
            "output_csv": str(self.csv_path),
            "job_context": context,
        }
        self.save_metadata_json(data)
        return data

    def _crawl(
        self,
        seeds: list[str],
        max_pages: int,
        depth_limit: int,
        per_domain: int,
    ) -> list[dict[str, Any]]:
        import logging as _logging

        import scrapy
        from scrapy.crawler import CrawlerProcess

        # Keep stdout clean (only the final JSON). Send any Scrapy logging to
        # stderr so the ASAGUS backend's stdout JSON contract is not polluted.
        _logging.basicConfig(stream=sys.stderr, level=_logging.ERROR)

        collected: dict[str, dict[str, Any]] = {}
        target_limit = max(self.limit, 5)

        class BusinessSpider(scrapy.Spider):
            name = "asagus_business"
            start_urls = seeds
            custom_settings = {
                "ROBOTSTXT_OBEY": True,
                "CONCURRENT_REQUESTS": 16,
                "DOWNLOAD_TIMEOUT": 20,
                "DEPTH_LIMIT": depth_limit,
                "CLOSESPIDER_PAGECOUNT": max_pages,
                "CLOSESPIDER_ITEMCOUNT": target_limit,
                "LOG_ENABLED": False,
                "USER_AGENT": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                "RETRY_ENABLED": True,
                "RETRY_TIMES": 1,
                "AUTOTHROTTLE_ENABLED": True,
            }

            def parse(spider_self, response):  # noqa: N805
                rec = _extract_record(response)
                if rec:
                    key = rec.get("website_url") or response.url
                    dom = urlparse(key).netloc.lower()
                    if dom and dom not in collected:
                        collected[dom] = rec

                if len(collected) >= target_limit:
                    return

                base_dom = urlparse(response.url).netloc.lower()
                followed = 0
                for href in response.css("a::attr(href)").getall():
                    if followed >= per_domain:
                        break
                    abs_url = urljoin(response.url, href)
                    if urlparse(abs_url).netloc.lower() != base_dom:
                        continue
                    if CONTACT_HINT_RE.search(abs_url):
                        followed += 1
                        yield response.follow(abs_url, callback=spider_self.parse)

        process = CrawlerProcess(
            settings={"TELNETCONSOLE_ENABLED": False, "LOG_ENABLED": False},
            install_root_handler=False,
        )
        process.crawl(BusinessSpider)
        process.start()  # blocks until done

        return list(collected.values())


def main() -> None:
    print(json.dumps(ScrapyWorkerAdapter().run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
