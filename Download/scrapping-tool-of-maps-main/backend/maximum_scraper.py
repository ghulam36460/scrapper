"""
Maximum Mode Scraper - The Ultimate Lead Extraction Engine

Combines EVERY available source in one run:
  1. Google Maps (primary, Playwright)
  2. Direct Web Search  (DuckDuckGo + Bing, HTTP-only)
  3. Deep website analysis  (multi-page HTTP crawl)
  4. Google Search cross-verification (Playwright)
  5. Business Extractor engine
  6. Email Extractor engine
  7. Full cross-verification of all findings

All results are deduplicated, merged and scored.
Produces the highest-quality leads of any mode.
"""

import logging
import random
import re
import time
import concurrent.futures
from dataclasses import dataclass, field
from threading import Event, Lock, local as thread_local
from typing import Callable, Dict, List, Optional, Set, Any
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page, BrowserContext
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from deep_scraper import (
    CaptchaDetectedError, BusinessData,
    normalize_phone, extract_emails, extract_whatsapp,
    extract_social_handle, detect_chatbot, detect_analytics, detect_cms,
    INSTAGRAM_PATTERNS, FACEBOOK_PATTERNS, TWITTER_PATTERNS,
    LINKEDIN_PATTERNS, TIKTOK_PATTERNS, YOUTUBE_PATTERNS,
    WHATSAPP_PATTERNS, EMAIL_PATTERNS, CONTACT_PAGES,
)
from business_extractor import WebsiteAnalyzer, analyze_website
from email_extractor import WebsiteExtractor
from web_scraper import WebBusinessScraper, _extract_emails, _extract_phones
from web_scraper import _extract_whatsapp as _web_extract_wa
from web_scraper import _extract_socials, _get_host, _is_valid_business_url
from maps_city_coverage import build_citywide_queries
from url_filters import is_business_website, normalize_business_website
from scrape_history import get_history
import concurrency_config as cc


# ============================================================================
# CONFIGURATION
# ============================================================================

MAX_RESULTS_CAP = 500
RESULT_SCAN_WINDOW = 320
CITYWIDE_QUERY_LIMIT = 30
MAP_STAGNANT_ROUNDS = 22
MAP_SCROLL_DELAY_MIN = 0.28
MAP_SCROLL_DELAY_MAX = 0.55
REQUEST_TIMEOUT = 15
QUERY_RETRY_ATTEMPTS = 2
QUERY_RETRY_BASE_WAIT_MS = 2500
CAPTCHA_MANUAL_WAIT_MS = 180_000
CAPTCHA_POLL_MS = 1_500
CAPTCHA_MARKERS = (
    "unusual traffic", "detected unusual", "recaptcha",
    "verify you are human", "not a robot", "g-recaptcha",
    "our systems have detected unusual traffic", "sorry/index",
)

ULTRA_CONTACT_PAGES = [
    "", "/contact", "/contact-us", "/contactus",
    "/about", "/about-us", "/aboutus", "/team",
    "/reach-us", "/get-in-touch", "/connect",
    "/social", "/follow-us", "/support", "/help",
    "/info", "/location", "/locations",
]

PHONE_REGEX = re.compile(r"(\+?\d[\d\s()\-\.]{6,}\d)")


# ============================================================================
# DATA CLASS
# ============================================================================

@dataclass
class MaximumBusinessData:
    """Full business record with every extractable field."""
    name: str = ""
    phone: str = ""
    website: str = ""
    has_website: bool = False
    address: str = ""
    rating: float = 0.0
    review_count: int = 0
    business_hours: str = ""
    category: str = ""
    plus_code: str = ""
    google_maps_url: str = ""

    emails: List[str] = field(default_factory=list)
    whatsapp_numbers: List[str] = field(default_factory=list)
    additional_phones: List[str] = field(default_factory=list)

    instagram: str = ""
    facebook: str = ""
    twitter: str = ""
    linkedin: str = ""
    tiktok: str = ""
    youtube: str = ""

    has_chatbot: bool = False
    chatbot_type: str = ""
    has_google_analytics: bool = False
    has_meta_pixel: bool = False
    cms_platform: str = ""
    is_automated: bool = False

    extraction_quality: str = "unknown"
    verification_score: int = 0
    data_sources: List[str] = field(default_factory=list)
    source_type: str = "maps"  # "maps" | "web" | "both"

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "phone": self.phone,
            "email": self.emails[0] if self.emails else "",
            "all_emails": "; ".join(self.emails),
            "whatsapp": self.whatsapp_numbers[0] if self.whatsapp_numbers else "",
            "all_whatsapp": "; ".join(self.whatsapp_numbers),
            "website": self.website,
            "has_website": "Yes" if self.has_website else "No",
            "address": self.address,
            "rating": self.rating,
            "review_count": self.review_count,
            "category": self.category,
            "business_hours": self.business_hours,
            "instagram": self.instagram,
            "facebook": self.facebook,
            "twitter": self.twitter,
            "linkedin": self.linkedin,
            "tiktok": self.tiktok,
            "youtube": self.youtube,
            "has_chatbot": "Yes" if self.has_chatbot else "No",
            "chatbot_type": self.chatbot_type,
            "has_google_analytics": "Yes" if self.has_google_analytics else "No",
            "has_meta_pixel": "Yes" if self.has_meta_pixel else "No",
            "cms_platform": self.cms_platform,
            "is_automated": "Yes" if self.is_automated else "No",
            "quality_score": self.extraction_quality,
            "verification_score": self.verification_score,
            "data_sources": ", ".join(self.data_sources),
            "google_maps_url": self.google_maps_url,
        }

    def calculate_quality(self) -> str:
        score = sum([
            bool(self.name),
            bool(self.phone),
            len(self.emails) >= 1,
            len(self.emails) >= 1,          # double weight
            bool(self.whatsapp_numbers),
            bool(self.whatsapp_numbers),    # double weight
            bool(self.website),
            bool(self.address),
            bool(self.instagram),
            bool(self.facebook),
            bool(self.has_chatbot or self.has_google_analytics),
            len(self.data_sources) >= 3,    # multi-source bonus
            len(self.data_sources) >= 3,
        ])
        if score >= 10:
            return "ultra"
        elif score >= 7:
            return "high"
        elif score >= 4:
            return "medium"
        return "low"

    def calc_verification(self) -> int:
        return min(100, len(self.data_sources) * 15 + (
            20 if self.emails else 0) + (
            15 if self.whatsapp_numbers else 0) + (
            10 if self.instagram or self.facebook else 0) + (
            10 if self.name and self.phone and self.address else 0))


# ============================================================================
# MAXIMUM SCRAPER
# ============================================================================

class MaximumScraper:
    """
    Maximum Mode: combines Maps scraping + direct web scraping + all
    analysis engines + cross-verification in a single pipeline.

    Pipeline:
        Phase A  –  Google Maps discovery & extraction  (Playwright)
        Phase B  –  Web search discovery  (DuckDuckGo + Bing, HTTP)
        Phase C  –  Deep website analysis on every unique website found
        Phase D  –  Google Search verification for social/contact gaps
        Phase E  –  Deduplication & merging of A+B results
        Phase F  –  Quality scoring & history tracking
    """

    def __init__(
        self,
        max_results: int = 50,
        headless: bool = False,
        min_delay: float = 0.7,
        max_delay: float = 1.6,
        website_filter: str = "all",
        deep_search: bool = True,
        verify_socials: bool = True,
        skip_duplicates: bool = True,
        logger: Optional[logging.Logger] = None,
        progress_callback: Optional[Callable[[Dict], None]] = None,
    ) -> None:
        self.max_results = max(1, min(max_results, MAX_RESULTS_CAP))
        self.headless = headless
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.website_filter = website_filter if website_filter in {"all", "with", "without"} else "all"
        self.deep_search = deep_search
        self.verify_socials = verify_socials
        self.skip_duplicates = skip_duplicates
        self.log = logger or logging.getLogger(__name__)
        self.progress_callback = progress_callback

        self._website_cache: Dict[str, Dict] = {}
        self._google_cache: Dict[str, Optional[Dict]] = {}
        self._results_lock = Lock()
        self._website_cache_lock = Lock()
        self._google_cache_lock = Lock()
        # Per-thread Playwright resources (sync API is not thread-safe across threads)
        self._thread_local = thread_local()
        self._thread_browsers: List = []
        self._thread_browsers_lock = Lock()
        # Concurrent Playwright tabs for Maps extraction (auto-sized to CPU)
        self.page_workers = max(1, min(cc.MAPS_PAGE_WORKERS, self.max_results))

        self.history = get_history(logger)
        self.web_scraper = WebBusinessScraper(
            max_results=max(10, self.max_results // 2),
            logger=logger,
        )
        self.email_extractor = WebsiteExtractor(timeout=12)

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        })

    # ------------------------------------------------------------------
    # PUBLIC ENTRY POINT
    # ------------------------------------------------------------------

    def scrape(
        self,
        keyword: str,
        location: str,
        stop_event: Optional[Event] = None,
    ) -> List[Dict[str, str]]:
        stop_event = stop_event or Event()

        if self.skip_duplicates:
            stats = self.history.get_stats(keyword, location)
            self.log.info(
                "📊 History: %d previously scraped for this search",
                stats.get("search_total", 0),
            )

        # ---- Phase B: Web search (runs parallel with Maps) ----
        web_leads: List[Dict] = []
        web_future = None
        web_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            if not stop_event.is_set():
                web_future = web_executor.submit(
                    self.web_scraper.scrape, keyword, location, stop_event
                )
        except Exception as exc:
            self.log.debug("Web scraper launch error: %s", exc)

        # ---- Phase A: Google Maps extraction (Playwright) ----
        maps_leads: List[Dict] = []
        try:
            maps_leads = self._run_maps_phase(keyword, location, stop_event)
        except Exception as exc:
            self.log.error("Maps phase error: %s", exc)

        # Collect web results
        if web_future:
            try:
                web_leads = web_future.result(timeout=120) or []
            except Exception as exc:
                self.log.debug("Web scraper result error: %s", exc)
        web_executor.shutdown(wait=False)

        self.log.info(
            "🔀 Merging: %d from Maps + %d from Web", len(maps_leads), len(web_leads)
        )

        # ---- Phase E: Deduplicate & merge ----
        merged = self._merge_leads(maps_leads, web_leads, keyword, location)

        # ---- Phase C/D: Deep analysis on any missing data ----
        merged = self._deep_enrich(merged, keyword, location, stop_event)

        # ---- Phase F: Score, save history, return ----
        for lead in merged:
            if isinstance(lead, dict):
                lead.setdefault("quality_score", "medium")
                lead.setdefault("whatsapp_wa_me_links", self._build_wa_links(lead))

        if self.skip_duplicates and merged:
            self.history.add_batch_to_history(merged, keyword, location)

        self.log.info("✅ Maximum mode completed: %d leads total", len(merged))
        return merged

    # ------------------------------------------------------------------
    # PHASE A: MAPS
    # ------------------------------------------------------------------

    def _run_maps_phase(self, keyword: str, location: str, stop_event: Event) -> List[Dict]:
        search_queries = build_citywide_queries(keyword, location, max_queries=CITYWIDE_QUERY_LIMIT)
        if not search_queries:
            return []

        dup_buffer = min(12, max(2, self.max_results // 8)) if self.skip_duplicates else 0
        target = self.max_results + dup_buffer

        with sync_playwright() as p:
            browser = p.chromium.launch(**cc.launch_kwargs(self.headless))
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1400, "height": 1000},
            )
            try:
                page = context.new_page()
                discovered: List[str] = []
                seen: Set[str] = set()
                per_q = max(10, (target + len(search_queries) - 1) // len(search_queries))

                for query in search_queries:
                    if stop_event.is_set() or len(discovered) >= target:
                        break
                    remaining = target - len(discovered)
                    urls = self._search_with_retry(page, query, stop_event, min(per_q, remaining))
                    for url in urls:
                        if url and url not in seen:
                            seen.add(url)
                            discovered.append(url)
                            if len(discovered) >= target:
                                break

                leads = self._extract_maps_leads(context, discovered[:target], keyword, location, stop_event)
                return [ld.to_dict() for ld in leads]
            finally:
                context.close()
                browser.close()

    def _search_with_retry(self, page: Page, query: str, stop_event: Event, target: int) -> List[str]:
        for attempt in range(QUERY_RETRY_ATTEMPTS + 1):
            if stop_event.is_set():
                break
            try:
                self._open_maps_search(page, query)
                return self._collect_place_urls(page, stop_event, target_count=target)
            except CaptchaDetectedError as exc:
                if attempt >= QUERY_RETRY_ATTEMPTS:
                    raise
                page.wait_for_timeout(QUERY_RETRY_BASE_WAIT_MS * (attempt + 1))
                try:
                    page.goto("https://www.google.com/maps", timeout=45_000)
                    self._accept_consent(page)
                except Exception:
                    pass
        return []

    def _open_maps_search(self, page: Page, query: str) -> None:
        encoded = quote_plus(query)
        page.goto(f"https://www.google.com/maps/search/{encoded}", timeout=90_000)
        page.wait_for_timeout(1_500)
        self._accept_consent(page)
        self._check_captcha(page)
        if self._wait_selector(page, ["div[role='feed']", "a.hfpxzc"], 45_000):
            self._delay()
            return
        inp = self._find_search_input(page)
        if inp:
            inp.fill(query)
            self._delay()
            inp.press("Enter")
        if not self._wait_selector(page, ["div[role='feed']", "a.hfpxzc", "h1.DUwDvf"], 45_000):
            raise RuntimeError("Maps results did not load")
        self._delay()
        self._check_captcha(page)

    def _collect_place_urls(self, page: Page, stop_event: Event, target_count: int = 50) -> List[str]:
        discovered: List[str] = []
        seen: Set[str] = set()
        stagnant = 0
        max_stagnant = MAP_STAGNANT_ROUNDS + 4

        if "/maps/place/" in (page.url or ""):
            return [page.url]

        while len(discovered) < target_count and stagnant < max_stagnant and not stop_event.is_set():
            before = len(discovered)
            try:
                hrefs = page.eval_on_selector_all(
                    "a.hfpxzc",
                    "els => els.map(el => el.getAttribute('href') || '').filter(Boolean)",
                )
            except Exception:
                hrefs = []

            for href in hrefs[max(0, len(hrefs) - RESULT_SCAN_WINDOW):]:
                if stop_event.is_set() or len(discovered) >= target_count:
                    break
                if href and href not in seen:
                    seen.add(href)
                    discovered.append(href)

            stagnant = 0 if len(discovered) > before else stagnant + 1

            feed = page.locator("div[role='feed']").first
            try:
                feed.evaluate("el => el.scrollBy(0, el.scrollHeight)")
            except Exception:
                page.mouse.wheel(0, 4000)
            self._delay(MAP_SCROLL_DELAY_MIN, MAP_SCROLL_DELAY_MAX)
            self._check_captcha(page)

        return discovered

    def _extract_maps_leads(
        self,
        context: BrowserContext,
        place_urls: List[str],
        keyword: str,
        location: str,
        stop_event: Event,
    ) -> List["MaximumBusinessData"]:
        leads: List[MaximumBusinessData] = []
        skipped = 0
        existing_ids: Set[str] = set()
        if self.skip_duplicates:
            existing_ids = self.history.get_existing_business_ids(keyword, location)

        # ------------------------------------------------------------------
        # PARALLEL extraction: process many listings concurrently, each in its
        # own browser tab. Auto-sized to the laptop's logical CPU count so all
        # cores / hyper-threads are kept busy. Thread-safe shared counters.
        # ------------------------------------------------------------------
        workers = max(1, min(self.page_workers, len(place_urls)))
        captcha_flag = {"hit": False}
        processed = {"n": 0}
        total = len(place_urls)

        def _enough() -> bool:
            with self._results_lock:
                return len(leads) >= self.max_results

        def _worker(place_url: str):
            if stop_event.is_set() or captcha_flag["hit"] or _enough():
                return
            tctx = self._get_thread_context()  # per-thread browser context (sync API is not thread-safe across threads)
            if tctx is None:
                return
            page = tctx.new_page()
            try:
                data = self._extract_single_maps_listing(page, place_url)
                if not data or not self._passes_filter(data.website):
                    return

                biz_id = None
                if self.skip_duplicates and existing_ids:
                    biz_id = self.history.get_business_id(data.to_dict())

                data.data_sources.append("google_maps")
                data.extraction_quality = data.calculate_quality()
                data.verification_score = data.calc_verification()

                with self._results_lock:
                    if biz_id and biz_id in existing_ids:
                        nonlocal_skip[0] += 1
                        return
                    if len(leads) >= self.max_results:
                        return
                    leads.append(data)

                if self.progress_callback:
                    try:
                        self.progress_callback(data.to_dict())
                    except Exception:
                        pass
            except CaptchaDetectedError:
                captcha_flag["hit"] = True
            except Exception as exc:
                self.log.warning("Maps listing error %s: %s", place_url, exc)
            finally:
                try:
                    page.close()
                except Exception:
                    pass
                with self._results_lock:
                    processed["n"] += 1
                    if processed["n"] % 5 == 0 or processed["n"] == total:
                        self.log.info(
                            "🗺️  Maps %d/%d (collected %d, skipped %d, %d tabs)",
                            processed["n"], total, len(leads), nonlocal_skip[0], workers,
                        )

        nonlocal_skip = [skipped]
        self.log.info("⚡ Parallel Maps extraction: %d tabs across %d listings", workers, total)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_worker, url) for url in place_urls]
            for fut in concurrent.futures.as_completed(futures):
                if (stop_event.is_set() or captcha_flag["hit"] or _enough()):
                    for f2 in futures:
                        f2.cancel()
                # surface captcha to caller
                exc = fut.exception()
                if isinstance(exc, CaptchaDetectedError):
                    captcha_flag["hit"] = True

        # Tear down all per-thread browsers/playwright instances.
        self._shutdown_thread_contexts()

        if captcha_flag["hit"]:
            raise CaptchaDetectedError("Captcha detected during parallel Maps extraction")

        return leads[: self.max_results]

    def _extract_single_maps_listing(self, page: Page, place_url: str) -> Optional["MaximumBusinessData"]:
        for attempt in range(2):
            try:
                page.goto(place_url, timeout=60_000)
                page.wait_for_timeout(1_200)
                self._check_captcha(page)

                data = MaximumBusinessData()
                data.google_maps_url = place_url
                data.name = self._safe_text(page, "h1.DUwDvf", "h1")
                data.phone = self._extract_phone(page)
                data.website = self._extract_website(page)
                data.has_website = bool(data.website)
                data.address = self._extract_address(page)
                data.rating, data.review_count = self._extract_rating(page)
                data.category = self._extract_category(page)
                data.business_hours = self._extract_hours(page)

                # Social links visible on Maps panel
                gmaps_socials = self._extract_gmaps_socials(page)
                data.instagram = gmaps_socials.get("instagram", "")
                data.facebook = gmaps_socials.get("facebook", "")
                data.twitter = gmaps_socials.get("twitter", "")

                # Deep website analysis
                if data.website:
                    cache_key = self._cache_key(data.website)
                    with self._website_cache_lock:
                        site_data = self._website_cache.get(cache_key)
                    if site_data is None:
                        site_data = self._analyze_website_full(data.website)
                        with self._website_cache_lock:
                            self._website_cache[cache_key] = site_data

                    data.emails = site_data.get("emails", [])
                    data.whatsapp_numbers = site_data.get("whatsapp_numbers", [])
                    socials = site_data.get("socials", {})
                    if not data.instagram:
                        data.instagram = socials.get("instagram", "")
                    if not data.facebook:
                        data.facebook = socials.get("facebook", "")
                    if not data.twitter:
                        data.twitter = socials.get("twitter", "")
                    data.linkedin = socials.get("linkedin", "")
                    data.tiktok = socials.get("tiktok", "")
                    data.youtube = socials.get("youtube", "")
                    data.has_chatbot = bool(site_data.get("has_chatbot"))
                    data.chatbot_type = site_data.get("chatbot_type", "")
                    data.has_google_analytics = bool(site_data.get("has_google_analytics"))
                    data.has_meta_pixel = bool(site_data.get("has_meta_pixel"))
                    data.cms_platform = site_data.get("cms_platform", "")
                    data.is_automated = data.has_chatbot
                    data.data_sources.append("website_analysis")
                elif data.phone:
                    norm = normalize_phone(data.phone)
                    if norm:
                        data.whatsapp_numbers = [norm]

                # Google Search cross-verification
                if self.deep_search and data.name:
                    gdata = self._google_verify(data.name, data.address or "")
                    if gdata:
                        if gdata.get("instagram") and not data.instagram:
                            data.instagram = gdata["instagram"]
                        if gdata.get("facebook") and not data.facebook:
                            data.facebook = gdata["facebook"]
                        if gdata.get("email") and not data.emails:
                            data.emails = [gdata["email"]]
                        if gdata.get("whatsapp") and not data.whatsapp_numbers:
                            data.whatsapp_numbers = [gdata["whatsapp"]]
                        data.data_sources.append("google_search")

                return data

            except CaptchaDetectedError:
                raise
            except Exception as exc:
                self.log.warning("Listing attempt %d failed: %s", attempt + 1, exc)
                self._delay(1.2, 2.2)
        return None

    # ------------------------------------------------------------------
    # PHASE C: DEEP WEBSITE ANALYSIS
    # ------------------------------------------------------------------

    def _analyze_website_full(self, website_url: str) -> Dict:
        """HTTP-crawl a site with WebsiteExtractor + BusinessExtractor."""
        result: Dict = {
            "emails": [], "whatsapp_numbers": [], "socials": {},
            "has_chatbot": False, "chatbot_type": "",
            "has_google_analytics": False, "has_meta_pixel": False,
            "cms_platform": "",
        }
        if not website_url:
            return result
        if not website_url.startswith(("http://", "https://")):
            website_url = f"https://{website_url}"
        try:
            pages = self.email_extractor.crawl_pages(
                website_url,
                max_pages=5,
                max_total_time_sec=12,
                priority_only=True,
            )
            if pages:
                corpus = "\n\n".join(p.html for p in pages if p.html)
                pa = analyze_website(corpus, website_url)
                result["emails"] = list(dict.fromkeys(pa.get("emails", [])))
                result["whatsapp_numbers"] = list(dict.fromkeys(pa.get("whatsapp_numbers", [])))
                result["socials"] = pa.get("socials", {}) or {}
                result["has_chatbot"] = bool(pa.get("has_chatbot"))
                result["chatbot_type"] = pa.get("chatbot_type", "") or ""
                result["has_google_analytics"] = bool(pa.get("has_google_analytics"))
                result["has_meta_pixel"] = bool(pa.get("has_meta_pixel"))
                result["cms_platform"] = pa.get("cms_platform", "") or ""
        except Exception as exc:
            self.log.debug("Website analysis failed for %s: %s", website_url, exc)
        return result

    # ------------------------------------------------------------------
    # PHASE D: GOOGLE SEARCH VERIFICATION
    # ------------------------------------------------------------------

    def _google_verify(self, name: str, address: str) -> Optional[Dict]:
        cache_key = f"{name}|{address}".lower()
        with self._google_cache_lock:
            if cache_key in self._google_cache:
                return self._google_cache[cache_key]
        result: Dict = {}
        query = f'"{name}" {address} contact email instagram'
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            }
            url = f"https://www.google.com/search?q={quote_plus(query)}&num=5"
            resp = self.session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code < 400:
                html = resp.text
                emails = _extract_emails(html)
                wa = _web_extract_wa(html)
                socials = _extract_socials(html)
                if emails:
                    result["email"] = emails[0]
                if wa:
                    result["whatsapp"] = wa[0]
                result.update(socials)
            time.sleep(random.uniform(0.4, 0.9))
        except Exception as exc:
            self.log.debug("Google verify failed for %s: %s", name, exc)
        with self._google_cache_lock:
            self._google_cache[cache_key] = result or None
        return result or None

    # ------------------------------------------------------------------
    # PHASE E: MERGE
    # ------------------------------------------------------------------

    def _merge_leads(
        self,
        maps_leads: List[Dict],
        web_leads: List[Dict],
        keyword: str,
        location: str,
    ) -> List[Dict]:
        """
        Merge Maps and Web leads, deduplicating by website host or name+phone.
        Maps leads take priority; web leads fill gaps or add unique entries.
        """
        merged: List[Dict] = list(maps_leads)
        seen_hosts: Set[str] = set()
        seen_names: Set[str] = set()

        for lead in maps_leads:
            host = _get_host(lead.get("website", ""))
            if host:
                seen_hosts.add(host)
            name_key = re.sub(r"\W+", "", (lead.get("name", "") or "").lower())
            if name_key:
                seen_names.add(name_key)

        for web_lead in web_leads:
            host = _get_host(web_lead.get("website", ""))
            name_key = re.sub(r"\W+", "", (web_lead.get("name", "") or "").lower())

            if host and host in seen_hosts:
                # Cross-enrich matching Maps lead
                for maps_lead in merged:
                    if _get_host(maps_lead.get("website", "")) == host:
                        self._fill_missing(maps_lead, web_lead)
                        src = maps_lead.get("data_sources", "")
                        if "web_search" not in src:
                            maps_lead["data_sources"] = (src + ", web_search").strip(", ")
                        break
                continue

            if name_key and name_key in seen_names:
                continue

            # New unique lead from web
            if host:
                seen_hosts.add(host)
            if name_key:
                seen_names.add(name_key)
            web_lead["source_type"] = "web"
            merged.append(web_lead)

        return merged

    def _fill_missing(self, target: Dict, source: Dict) -> None:
        """Fill empty fields in target with values from source."""
        for key in ["email", "phone", "whatsapp", "instagram", "facebook",
                    "twitter", "linkedin", "tiktok", "youtube", "address"]:
            if not target.get(key) and source.get(key):
                target[key] = source[key]
        # Merge all_emails
        if source.get("all_emails") and not target.get("all_emails"):
            target["all_emails"] = source["all_emails"]
        if source.get("all_whatsapp") and not target.get("all_whatsapp"):
            target["all_whatsapp"] = source["all_whatsapp"]

    # ------------------------------------------------------------------
    # PHASE C (post-merge): Deep enrich any lead missing email/whatsapp
    # ------------------------------------------------------------------

    def _deep_enrich(
        self,
        leads: List[Dict],
        keyword: str,
        location: str,
        stop_event: Event,
    ) -> List[Dict]:
        """HTTP-crawl websites for any lead still missing email or WhatsApp."""
        targets = [
            (i, ld) for i, ld in enumerate(leads)
            if ld.get("website") and is_business_website(ld["website"])
               and not ld.get("email") and not ld.get("whatsapp")
        ]
        if not targets:
            return leads

        self.log.info("🔍 Deep enriching %d leads with missing contact data", len(targets))

        def _enrich_one(idx_lead):
            idx, ld = idx_lead
            if stop_event.is_set():
                return
            try:
                enrichment = self.email_extractor.enrich(
                    ld["website"],
                    fallback_phone=ld.get("phone", ""),
                    max_pages=5,
                    max_total_time_sec=12,
                    priority_only=True,
                )
                if enrichment.get("email"):
                    leads[idx]["email"] = enrichment["email"]
                    leads[idx]["all_emails"] = enrichment["email"]
                if enrichment.get("whatsapp"):
                    leads[idx]["whatsapp"] = enrichment["whatsapp"]
                    leads[idx]["all_whatsapp"] = enrichment["whatsapp"]
                    leads[idx]["whatsapp_wa_me_links"] = self._build_wa_links(leads[idx])
            except Exception:
                pass

        enrich_workers = max(1, min(cc.ENRICH_WORKERS, len(targets)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=enrich_workers) as ex:
            list(ex.map(_enrich_one, targets))

        return leads

    # ------------------------------------------------------------------
    # PER-THREAD PLAYWRIGHT (enables safe multi-tab parallel extraction)
    # ------------------------------------------------------------------

    def _get_thread_context(self):
        """Return a BrowserContext owned by the calling worker thread.

        The Playwright sync API forbids driving a page/context from a thread
        other than the one that created it. So each worker thread lazily spins
        up its own Playwright + Chromium + context and reuses it for every
        listing that thread processes.
        """
        ctx = getattr(self._thread_local, "context", None)
        if ctx is not None:
            return ctx
        try:
            from playwright.sync_api import sync_playwright as _sp
            pw = _sp().start()
            browser = pw.chromium.launch(**cc.launch_kwargs(self.headless))
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1400, "height": 1000},
            )
        except Exception as exc:
            self.log.error("Failed to start per-thread browser: %s", exc)
            return None

        self._thread_local.pw = pw
        self._thread_local.browser = browser
        self._thread_local.context = context
        with self._thread_browsers_lock:
            self._thread_browsers.append((pw, browser, context))
        return context

    def _shutdown_thread_contexts(self) -> None:
        """Close every per-thread browser spawned during extraction."""
        with self._thread_browsers_lock:
            registry = list(self._thread_browsers)
            self._thread_browsers.clear()
        for pw, browser, context in registry:
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
            try:
                pw.stop()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # PLAYWRIGHT HELPERS
    # ------------------------------------------------------------------

    def _accept_consent(self, page: Page) -> None:
        for sel in ["button:has-text('Accept all')", "button:has-text('I agree')", "button:has-text('Accept')"]:
            try:
                btn = page.locator(sel).first
                if btn.count() > 0 and btn.is_visible():
                    btn.click(timeout=3_000)
                    page.wait_for_timeout(1_200)
                    return
            except Exception:
                pass

    def _find_search_input(self, page: Page):
        for sel in ["input#searchboxinput", "input[aria-label='Search Google Maps']", "input[name='q']"]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    loc.wait_for(state="visible", timeout=6_000)
                    return loc
            except Exception:
                pass
        return None

    def _wait_selector(self, page: Page, selectors: List[str], timeout_ms: int) -> bool:
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            for sel in selectors:
                try:
                    if page.locator(sel).first.count() > 0:
                        return True
                except Exception:
                    pass
            page.wait_for_timeout(400)
        return False

    def _check_captcha(self, page: Page) -> None:
        try:
            content = page.content().lower()
        except Exception:
            return
        if any(m in content for m in CAPTCHA_MARKERS):
            if not self.headless:
                deadline = time.time() + CAPTCHA_MANUAL_WAIT_MS / 1000
                self.log.warning("Captcha detected – waiting for manual solve…")
                while time.time() < deadline:
                    page.wait_for_timeout(CAPTCHA_POLL_MS)
                    try:
                        c = page.content().lower()
                    except Exception:
                        break
                    if not any(m in c for m in CAPTCHA_MARKERS):
                        return
            raise CaptchaDetectedError("Captcha detected")

    def _safe_text(self, page: Page, selector: str, fallback: str = "") -> str:
        for sel in ([selector] + ([fallback] if fallback else [])):
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    val = loc.inner_text(timeout=4_000).strip()
                    if val:
                        return val
            except Exception:
                pass
        return ""

    def _extract_phone(self, page: Page) -> str:
        for sel in ["button[data-item-id^='phone:tel:']", "button[aria-label*='Phone']", "button[aria-label*='phone']"]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    raw = loc.inner_text(timeout=3_500).strip()
                    m = PHONE_REGEX.search(raw)
                    if m:
                        return m.group(1).strip()
            except Exception:
                pass
        return ""

    def _extract_website(self, page: Page) -> str:
        for sel in ["a[data-item-id='authority']", "a[aria-label*='Website']", "a[aria-label*='website']"]:
            try:
                anchor = page.locator(sel).first
                if anchor.count() > 0:
                    href = anchor.get_attribute("href") or ""
                    if href.startswith("http"):
                        return normalize_business_website(href)
            except Exception:
                pass
        return ""

    def _extract_address(self, page: Page) -> str:
        for sel in ["button[data-item-id='address']", "button[aria-label*='Address']"]:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    return loc.inner_text(timeout=3_000).strip()
            except Exception:
                pass
        return ""

    def _extract_rating(self, page: Page):
        rating, reviews = 0.0, 0
        try:
            el = page.locator("span.ceNzKf, div.F7nice span[aria-hidden='true']").first
            if el.count() > 0:
                m = re.search(r"[\d.]+", el.inner_text(timeout=3_000))
                if m:
                    rating = float(m.group())
        except Exception:
            pass
        try:
            el = page.locator("span.UY7F9, button[jsaction*='review'] span").first
            if el.count() > 0:
                m = re.search(r"[\d,]+", el.inner_text(timeout=3_000).replace(",", ""))
                if m:
                    reviews = int(m.group())
        except Exception:
            pass
        return rating, reviews

    def _extract_category(self, page: Page) -> str:
        try:
            el = page.locator("button.DkEaL, span.DkEaL").first
            if el.count() > 0:
                return el.inner_text(timeout=3_000).strip()
        except Exception:
            pass
        return ""

    def _extract_hours(self, page: Page) -> str:
        try:
            el = page.locator("button[data-item-id*='oh'], button[aria-label*='hour']").first
            if el.count() > 0:
                return el.inner_text(timeout=3_000).strip()
        except Exception:
            pass
        return ""

    def _extract_gmaps_socials(self, page: Page) -> Dict[str, str]:
        socials: Dict[str, str] = {}
        try:
            links = page.eval_on_selector_all(
                "a[href*='instagram.com'], a[href*='facebook.com'], a[href*='twitter.com'], a[href*='x.com']",
                "els => els.map(el => el.href)"
            )
            for link in links:
                if "instagram.com" in link and "instagram" not in socials:
                    socials["instagram"] = link
                elif "facebook.com" in link and "facebook" not in socials:
                    socials["facebook"] = link
                elif ("twitter.com" in link or "x.com" in link) and "twitter" not in socials:
                    socials["twitter"] = link
        except Exception:
            pass
        return socials

    # ------------------------------------------------------------------
    # FILTER / UTILITIES
    # ------------------------------------------------------------------

    def _passes_filter(self, website: str) -> bool:
        has = is_business_website(website)
        if self.website_filter == "with":
            return has
        if self.website_filter == "without":
            return not has
        return True

    def _cache_key(self, url: str) -> str:
        parsed = urlparse(url if url.startswith("http") else f"https://{url}")
        host = (parsed.netloc or parsed.path).lower()
        return host[4:] if host.startswith("www.") else host

    def _build_wa_links(self, lead: Dict) -> str:
        raw = str(lead.get("all_whatsapp") or lead.get("whatsapp") or "")
        links = []
        for m in re.finditer(r"\+?\d[\d\s()\-.]{6,}\d", raw):
            digits = re.sub(r"\D", "", m.group())
            if len(digits) >= 8:
                links.append(f"https://wa.me/{digits}")
        return "; ".join(links)

    def _delay(self, mn: float = None, mx: float = None) -> None:
        time.sleep(random.uniform(
            mn if mn is not None else self.min_delay,
            mx if mx is not None else self.max_delay,
        ))
