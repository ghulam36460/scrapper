"""
Web Scraper - Direct Web Search & Scraping Engine
Scrapes businesses directly from the web (DuckDuckGo, Bing, Google Search)
without requiring Google Maps. Extracts contact data from search results and
business websites directly.

This module is used as an additional source in the "Maximum" extraction mode
to find businesses that may not appear on Google Maps, or to cross-verify
and supplement data found via Maps.
"""

import logging
import re
import time
import random
from typing import Dict, List, Optional, Set
from urllib.parse import quote_plus, urljoin, urlparse

import requests
import concurrent.futures
from threading import Lock
from bs4 import BeautifulSoup

try:
    from selectolax.parser import HTMLParser as SLHTMLParser
except ImportError:
    SLHTMLParser = None

from email_extractor import WebsiteExtractor
from url_filters import is_business_website, normalize_business_website
import concurrency_config as cc


# ============================================================================
# CONSTANTS
# ============================================================================

REQUEST_TIMEOUT = 15
MAX_SEARCH_RESULTS = 30
MAX_WEBSITE_PAGES = 6

SEARCH_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]

INVALID_DOMAINS = {
    "google.com", "google.co.uk", "google.com.pk",
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "youtube.com", "youtu.be", "tiktok.com",
    "wikipedia.org", "amazon.com", "ebay.com", "yelp.com",
    "tripadvisor.com", "yellowpages.com", "whitepages.com",
    "wa.me", "whatsapp.com", "t.me", "telegram.me",
    "reddit.com", "quora.com", "pinterest.com",
    "maps.google.com", "apple.com", "microsoft.com",
    "bing.com", "duckduckgo.com", "yahoo.com",
}

# Phone regex patterns
PHONE_PATTERNS = [
    re.compile(r"(\+\d{1,3}[\s\-\.]?\(?\d{1,4}\)?[\s\-\.]?\d{3,4}[\s\-\.]?\d{3,4})", re.I),
    re.compile(r"(\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4})", re.I),
    re.compile(r"(\+\d{10,15})", re.I),
    re.compile(r"tel:(\+?[\d\s\-\(\)]{7,15})", re.I),
]

# Email regex
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.I)

# WhatsApp patterns
WA_PATTERNS = [
    re.compile(r"(?:https?://)?wa\.me/(\+?\d{6,15})", re.I),
    re.compile(r"(?:https?://)?api\.whatsapp\.com/send\?phone=(\+?\d{6,15})", re.I),
]

SOCIAL_PATTERNS = {
    "instagram": re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9_\.]{1,30})/?", re.I),
    "facebook":  re.compile(r"(?:https?://)?(?:www\.)?facebook\.com/([a-zA-Z0-9\.]{1,50})/?", re.I),
    "twitter":   re.compile(r"(?:https?://)?(?:www\.)?(?:twitter|x)\.com/([a-zA-Z0-9_]{1,15})/?", re.I),
    "linkedin":  re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/(?:company|in)/([a-zA-Z0-9_\-]+)/?", re.I),
    "tiktok":    re.compile(r"(?:https?://)?(?:www\.)?tiktok\.com/@([a-zA-Z0-9_\.]+)/?", re.I),
    "youtube":   re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/(?:@|channel/|c/|user/)?([a-zA-Z0-9_\-]+)/?", re.I),
}

INVALID_HANDLES = {
    "share", "sharer", "intent", "dialog", "login", "signup", "home", "p",
    "explore", "accounts", "help", "settings", "search", "hashtag", "i",
    "direct", "stories", "reels", "live", "tv", "pages", "groups", "events",
    "marketplace", "gaming", "watch", "profile.php", "plugins",
}


# ============================================================================
# HELPERS
# ============================================================================

def _random_ua() -> str:
    return random.choice(SEARCH_USER_AGENTS)


def _get_host(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _is_valid_business_url(url: str) -> bool:
    host = _get_host(url)
    if not host:
        return False
    for bad in INVALID_DOMAINS:
        if host == bad or host.endswith(f".{bad}"):
            return False
    return url.startswith(("http://", "https://"))


def _extract_text(html: str) -> str:
    """Fast plain-text extraction from HTML."""
    if SLHTMLParser:
        try:
            tree = SLHTMLParser(html)
            return tree.text(separator=" ", strip=True)
        except Exception:
            pass
    try:
        soup = BeautifulSoup(html, "lxml")
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)


def _extract_emails(text: str) -> List[str]:
    found = []
    seen: Set[str] = set()
    for m in EMAIL_RE.finditer(text):
        e = m.group(0).lower().strip()
        if e in seen:
            continue
        # Filter obvious invalid emails
        if any(bad in e for bad in [".png", ".jpg", ".gif", ".svg", ".css", ".js"]):
            continue
        domain = e.split("@")[-1]
        if domain in {"example.com", "test.com", "domain.com", "yoursite.com"}:
            continue
        seen.add(e)
        found.append(e)
    return found[:5]


def _extract_phones(text: str) -> List[str]:
    found = []
    seen: Set[str] = set()
    for pattern in PHONE_PATTERNS:
        for m in pattern.finditer(text):
            raw = m.group(1).strip()
            digits = re.sub(r"\D", "", raw)
            if len(digits) < 7 or digits in seen:
                continue
            seen.add(digits)
            found.append(raw)
    return found[:3]


def _extract_whatsapp(text: str) -> List[str]:
    found = []
    seen: Set[str] = set()
    for pat in WA_PATTERNS:
        for m in pat.finditer(text):
            digits = re.sub(r"\D", "", m.group(1))
            if digits and digits not in seen:
                seen.add(digits)
                found.append("+" + digits if not digits.startswith("+") else digits)
    return found[:3]


def _extract_socials(html: str) -> Dict[str, str]:
    socials: Dict[str, str] = {}
    for platform, pat in SOCIAL_PATTERNS.items():
        m = pat.search(html)
        if m:
            handle = m.group(1).rstrip("/")
            if handle.lower() in INVALID_HANDLES:
                continue
            if platform == "instagram":
                socials[platform] = f"https://www.instagram.com/{handle}"
            elif platform == "facebook":
                socials[platform] = f"https://www.facebook.com/{handle}"
            elif platform == "twitter":
                socials[platform] = f"https://twitter.com/{handle}"
            elif platform == "linkedin":
                socials[platform] = f"https://www.linkedin.com/company/{handle}"
            elif platform == "tiktok":
                socials[platform] = f"https://www.tiktok.com/@{handle}"
            elif platform == "youtube":
                socials[platform] = f"https://www.youtube.com/{handle}"
    return socials


# ============================================================================
# SEARCH ENGINES
# ============================================================================

class DuckDuckGoSearcher:
    """Scrapes business listings from DuckDuckGo HTML search."""

    BASE_URL = "https://html.duckduckgo.com/html/"

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.log = logger or logging.getLogger(__name__)
        self.session = requests.Session()

    def search(self, query: str, max_results: int = 20) -> List[Dict[str, str]]:
        results: List[Dict[str, str]] = []
        headers = {
            "User-Agent": _random_ua(),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            resp = self.session.post(
                self.BASE_URL,
                data={"q": query, "b": ""},
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code >= 400:
                self.log.debug("DDG returned %d for query: %s", resp.status_code, query)
                return results

            soup = BeautifulSoup(resp.text, "lxml")
            for result in soup.select(".result"):
                title_el = result.select_one(".result__title a")
                snippet_el = result.select_one(".result__snippet")
                url_el = result.select_one(".result__url")

                title = title_el.get_text(strip=True) if title_el else ""
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                url = title_el.get("href", "") if title_el else ""
                display_url = url_el.get_text(strip=True) if url_el else ""

                if not url or not title:
                    continue
                if not url.startswith("http"):
                    url = f"https://{display_url}" if display_url else ""
                if not _is_valid_business_url(url):
                    continue

                results.append({"title": title, "snippet": snippet, "url": url})
                if len(results) >= max_results:
                    break

        except Exception as exc:
            self.log.debug("DDG search failed: %s", exc)

        return results


class BingSearcher:
    """Scrapes business listings from Bing search."""

    BASE_URL = "https://www.bing.com/search"

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.log = logger or logging.getLogger(__name__)
        self.session = requests.Session()

    def search(self, query: str, max_results: int = 20) -> List[Dict[str, str]]:
        results: List[Dict[str, str]] = []
        headers = {
            "User-Agent": _random_ua(),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            resp = self.session.get(
                self.BASE_URL,
                params={"q": query, "count": max_results},
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code >= 400:
                self.log.debug("Bing returned %d for query: %s", resp.status_code, query)
                return results

            soup = BeautifulSoup(resp.text, "lxml")
            for result in soup.select("li.b_algo"):
                title_el = result.select_one("h2 a")
                snippet_el = result.select_one(".b_caption p, .b_snippet")
                title = title_el.get_text(strip=True) if title_el else ""
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                url = title_el.get("href", "") if title_el else ""

                if not url or not title or not url.startswith("http"):
                    continue
                if not _is_valid_business_url(url):
                    continue

                results.append({"title": title, "snippet": snippet, "url": url})
                if len(results) >= max_results:
                    break

        except Exception as exc:
            self.log.debug("Bing search failed: %s", exc)

        return results


# ============================================================================
# MAIN WEB SCRAPER CLASS
# ============================================================================

class WebBusinessScraper:
    """
    Scrapes businesses directly from the web (DuckDuckGo + Bing search).

    Flow:
    1. Search DuckDuckGo + Bing for "{keyword} in {location}"
    2. Collect unique business URLs from search results
    3. For each URL, crawl the site and extract:
       - Business name (from title / h1 / og:site_name)
       - Phone numbers
       - Email addresses
       - WhatsApp numbers
       - Social media links (Instagram, Facebook, Twitter, etc.)
       - Address (if present)
    4. Return structured lead dicts compatible with Maps scraper output
    """

    def __init__(
        self,
        max_results: int = 20,
        logger: Optional[logging.Logger] = None,
        progress_callback=None,
    ):
        self.max_results = max(1, min(max_results, 100))
        self.log = logger or logging.getLogger(__name__)
        self.progress_callback = progress_callback
        self.ddg = DuckDuckGoSearcher(logger)
        self.bing = BingSearcher(logger)
        self.extractor = WebsiteExtractor(timeout=12)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": _random_ua()})

    def scrape(
        self,
        keyword: str,
        location: str,
        stop_event=None,
    ) -> List[Dict[str, str]]:
        """
        Search the web for businesses matching keyword + location,
        scrape each result page, and return structured leads.
        """
        from threading import Event
        stop_event = stop_event or Event()

        queries = self._build_queries(keyword, location)
        self.log.info("🌐 WebScraper: searching %d queries for '%s' in '%s'", len(queries), keyword, location)

        # Collect candidate URLs from search engines IN PARALLEL.
        # Every (engine, query) pair runs on its own thread so all queries hit
        # DuckDuckGo + Bing simultaneously instead of sequentially.
        candidate_urls: List[Dict[str, str]] = []
        seen_hosts: Set[str] = set()
        target_candidates = self.max_results * 3

        search_tasks = []
        for query in queries:
            search_tasks.append((self.ddg, query))
            search_tasks.append((self.bing, query))

        s_workers = max(1, min(cc.IO_WORKERS, len(search_tasks) or 1))
        all_results: List[Dict[str, str]] = []
        results_lock = Lock()

        def _run_search(task):
            engine, query = task
            if stop_event.is_set():
                return
            try:
                res = engine.search(query, max_results=15)
            except Exception:
                res = []
            if res:
                with results_lock:
                    all_results.extend(res)

        with concurrent.futures.ThreadPoolExecutor(max_workers=s_workers) as ex:
            list(ex.map(_run_search, search_tasks))

        for item in all_results:
            if len(candidate_urls) >= target_candidates:
                break
            url = item.get("url", "")
            host = _get_host(url)
            if not host or host in seen_hosts:
                continue
            if not _is_valid_business_url(url):
                continue
            seen_hosts.add(host)
            candidate_urls.append(item)

        self.log.info("🌐 WebScraper: found %d unique candidate URLs", len(candidate_urls))

        # Extract lead data from each URL IN PARALLEL (I/O-bound HTTP crawls).
        leads: List[Dict[str, str]] = []
        leads_lock = Lock()
        workers = max(1, min(cc.IO_WORKERS, len(candidate_urls) or 1))

        def _process(item: Dict[str, str]):
            with leads_lock:
                if len(leads) >= self.max_results:
                    return
            if stop_event.is_set():
                return
            url = item.get("url", "")
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            lead = self._extract_lead_from_site(url, title, snippet, keyword, location)
            if not lead:
                return
            with leads_lock:
                if len(leads) >= self.max_results:
                    return
                leads.append(lead)
            if self.progress_callback:
                try:
                    self.progress_callback(dict(lead))
                except Exception:
                    pass

        self.log.info("🌐 WebScraper: extracting %d candidates with %d parallel workers", len(candidate_urls), workers)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_process, item) for item in candidate_urls]
            for fut in concurrent.futures.as_completed(futures):
                if stop_event.is_set():
                    for f2 in futures:
                        f2.cancel()
                    break

        self.log.info("🌐 WebScraper: extracted %d leads from web", len(leads))
        return leads[: self.max_results]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_queries(self, keyword: str, location: str) -> List[str]:
        queries = [
            f"{keyword} {location}",
            f"{keyword} in {location}",
            f"best {keyword} {location}",
            f"{keyword} contact {location}",
            f"top {keyword} near {location}",
            f"{keyword} business {location} email phone",
        ]
        return queries

    def _extract_lead_from_site(
        self,
        url: str,
        title: str,
        snippet: str,
        keyword: str,
        location: str,
    ) -> Optional[Dict[str, str]]:
        """Fetch a business website and extract all contact data."""
        try:
            # Fast HTTP crawl via WebsiteExtractor
            pages = self.extractor.crawl_pages(url, max_pages=MAX_WEBSITE_PAGES)
            if not pages:
                # Fallback: single GET
                raw_html = self._safe_get(url)
                if not raw_html:
                    return None
                from email_extractor import CrawledPage
                pages = [CrawledPage(url=url, html=raw_html)]

            full_text = "\n\n".join(p.html for p in pages if p.html)
            plain_text = _extract_text(full_text)

            # Extract all data
            emails = _extract_emails(plain_text)
            phones = _extract_phones(plain_text)
            whatsapp = _extract_whatsapp(full_text)
            socials = _extract_socials(full_text)

            # Determine business name
            name = self._extract_name(pages[0].html, title) if pages else title

            # Determine address (best-effort)
            address = self._extract_address(plain_text, location)

            # Skip if no useful data found
            if not emails and not phones and not whatsapp and not socials:
                return None

            lead = {
                "name": name or title,
                "phone": phones[0] if phones else "",
                "email": emails[0] if emails else "",
                "all_emails": "; ".join(emails),
                "whatsapp": whatsapp[0] if whatsapp else "",
                "all_whatsapp": "; ".join(whatsapp),
                "website": url,
                "has_website": "Yes",
                "address": address,
                "rating": "",
                "review_count": "",
                "category": keyword,
                "business_hours": "",
                "instagram": socials.get("instagram", ""),
                "facebook": socials.get("facebook", ""),
                "twitter": socials.get("twitter", ""),
                "linkedin": socials.get("linkedin", ""),
                "tiktok": socials.get("tiktok", ""),
                "youtube": socials.get("youtube", ""),
                "has_chatbot": "",
                "chatbot_type": "",
                "has_google_analytics": "",
                "has_meta_pixel": "",
                "cms_platform": "",
                "is_automated": "",
                "quality_score": self._score_lead(emails, phones, whatsapp, socials),
                "verification_score": "",
                "data_sources": "web_search",
                "google_maps_url": "",
                "whatsapp_wa_me_links": self._build_wa_links(whatsapp),
                "source_type": "web",
            }
            return lead

        except Exception as exc:
            self.log.debug("Failed to extract from %s: %s", url, exc)
            return None

    def _safe_get(self, url: str) -> str:
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True, verify=False)
            if resp.status_code < 400:
                return resp.text
        except Exception:
            pass
        return ""

    def _extract_name(self, html: str, fallback: str) -> str:
        """Extract business name from HTML title/og tags/h1."""
        # og:site_name
        m = re.search(r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
        if m:
            return m.group(1).strip()
        # og:title
        m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
        if m:
            name = m.group(1).strip()
            # Strip common suffixes
            name = re.sub(r"\s*[-|–]\s*.*$", "", name).strip()
            if name:
                return name
        # <title>
        m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        if m:
            name = m.group(1).strip()
            name = re.sub(r"\s*[-|–]\s*.*$", "", name).strip()
            if name:
                return name
        # <h1>
        m = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.I)
        if m:
            return m.group(1).strip()
        return fallback

    def _extract_address(self, plain_text: str, location: str) -> str:
        """Try to find a street address mentioning the location."""
        location_lower = location.lower().strip().split(",")[0]
        lines = plain_text.split("\n")
        for line in lines:
            line_stripped = line.strip()
            if location_lower in line_stripped.lower() and len(line_stripped) > 10:
                # Likely an address line if it has digits and location name
                if re.search(r"\d", line_stripped):
                    return line_stripped[:120]
        return ""

    def _score_lead(
        self,
        emails: List[str],
        phones: List[str],
        whatsapp: List[str],
        socials: Dict[str, str],
    ) -> str:
        score = 0
        if emails:
            score += 3
        if phones:
            score += 2
        if whatsapp:
            score += 2
        if socials.get("instagram") or socials.get("facebook"):
            score += 2
        if socials.get("linkedin") or socials.get("twitter"):
            score += 1
        if score >= 7:
            return "high"
        elif score >= 4:
            return "medium"
        return "low"

    def _build_wa_links(self, numbers: List[str]) -> str:
        links = []
        for n in numbers:
            digits = re.sub(r"\D", "", n)
            if digits:
                links.append(f"https://wa.me/{digits}")
        return "; ".join(links)
