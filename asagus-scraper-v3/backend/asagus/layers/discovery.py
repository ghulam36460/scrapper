from __future__ import annotations

import asyncio
import re
from html import unescape
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import httpx

from asagus.models import SearchDiscoveryRequest, SearchDiscoveryResult, SearchEngine, URLCandidate, URLType


HREF_RE = re.compile(r"href=[\"']([^\"']+)", re.I)
CONTACT_MARKERS = ("contact", "about", "reach", "location", "branch", "team", "support")
SOCIAL_DOMAINS = ("facebook.com", "instagram.com", "x.com", "twitter.com", "linkedin.com")
DIRECTORY_DOMAINS = ("yelp.", "tripadvisor.", "yellowpages.", "foursquare.", "clutch.co", "sortlist.", "designrush.")
CONTACT_PATHS = ("/contact", "/contact-us", "/contactus", "/about", "/about-us", "/locations", "/branches")
LOW_VALUE_DOMAINS = (
    "google.",
    "bing.",
    "duckduckgo.",
    "startpage.",
    "youtube.",
    "youtu.be",
    "wikipedia.",
    "schema.org",
    "w3.org",
    "wordpress.org",
)


class SearchDiscoveryLayer:
    """Search-engine seed discovery using DDGS when network discovery is enabled."""

    def __init__(self, enable_network_search: bool = False) -> None:
        self.enable_network_search = enable_network_search

    async def discover(self, request: SearchDiscoveryRequest) -> list[SearchDiscoveryResult]:
        if not self.enable_network_search:
            return self._offline_discovery(request)
        try:
            results = await asyncio.to_thread(self._ddgs_search, request)
            if results:
                return results
        except Exception:
            pass
        return await asyncio.to_thread(self._html_search_fallback, request)

    def _ddgs_search(self, request: SearchDiscoveryRequest) -> list[SearchDiscoveryResult]:
        from ddgs import DDGS  # type: ignore

        results: list[SearchDiscoveryResult] = []
        seen: set[str] = set()
        backend = ",".join(engine.value for engine in request.engines)
        variants = self._query_variants(request)
        per_query = max(8, min(40, request.max_results // max(len(variants), 1) + 4))
        for query_index, query in enumerate(variants):
            try:
                rows = list(
                    DDGS(timeout=12).text(
                        query,
                        region=request.region,
                        safesearch=request.safesearch,
                        max_results=per_query,
                        backend=backend or "auto",
                    )
                )
            except Exception:
                continue
            for row in rows:
                url = str(row.get("href") or row.get("url") or "")
                key = self._url_key(url)
                if not url or key in seen:
                    continue
                seen.add(key)
                engine = self._engine_from_source(str(row.get("source") or request.engines[0].value))
                rank = len(results) + 1
                candidate = self._candidate_from_result(url, request, engine, rank)
                candidate.metadata["discovery_query"] = query
                candidate.metadata["query_variant"] = query_index
                results.append(
                    SearchDiscoveryResult(
                        title=str(row.get("title") or ""),
                        url=url,
                        snippet=str(row.get("body") or row.get("snippet") or ""),
                        engine=engine,
                        rank=rank,
                        candidate=candidate,
                    )
                )
                if len(results) >= request.max_results:
                    return results
        return results

    def _html_search_fallback(self, request: SearchDiscoveryRequest) -> list[SearchDiscoveryResult]:
        results: list[SearchDiscoveryResult] = []
        seen: set[str] = set()
        variants = self._query_variants(request)
        per_query = max(8, min(20, request.max_results // max(len(variants), 1) + 4))
        with httpx.Client(timeout=12, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
            for query_index, query in enumerate(variants):
                try:
                    response = client.get(f"https://html.duckduckgo.com/html/?q={quote_plus(query)}")
                except Exception:
                    continue
                if response.status_code >= 400:
                    continue
                for title, url, snippet in self._parse_duckduckgo_html(response.text):
                    key = self._url_key(url)
                    if not url or key in seen:
                        continue
                    seen.add(key)
                    rank = len(results) + 1
                    candidate = self._candidate_from_result(url, request, SearchEngine.duckduckgo, rank)
                    candidate.metadata["discovery_query"] = query
                    candidate.metadata["query_variant"] = query_index
                    candidate.metadata["search_fallback"] = "duckduckgo_html"
                    results.append(
                        SearchDiscoveryResult(
                            title=title,
                            url=url,
                            snippet=snippet,
                            engine=SearchEngine.duckduckgo,
                            rank=rank,
                            candidate=candidate,
                        )
                    )
                    if len(results) >= request.max_results:
                        return results
                    if rank >= per_query * max(query_index + 1, 1):
                        break
        return results

    def _parse_duckduckgo_html(self, html: str) -> list[tuple[str, str, str]]:
        rows: list[tuple[str, str, str]] = []
        pattern = re.compile(
            r"<a[^>]+class=[\"']result__a[\"'][^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>.*?(?:<a[^>]+class=[\"']result__snippet[\"'][^>]*>(.*?)</a>|<div[^>]+class=[\"']result__snippet[\"'][^>]*>(.*?)</div>)?",
            re.I | re.S,
        )
        for raw_url, raw_title, snippet_a, snippet_div in pattern.findall(html or ""):
            url = self._unwrap_duckduckgo_url(unescape(raw_url))
            title = self._clean_html(raw_title)
            snippet = self._clean_html(snippet_a or snippet_div)
            if url and title:
                rows.append((title, url, snippet))
        if rows:
            return rows
        for raw_url, raw_title in re.findall(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html or "", flags=re.I | re.S):
            title = self._clean_html(raw_title)
            url = self._unwrap_duckduckgo_url(unescape(raw_url))
            if title and url and not any(domain in urlparse(url).netloc.lower() for domain in LOW_VALUE_DOMAINS):
                rows.append((title, url, ""))
        return rows

    def _unwrap_duckduckgo_url(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
            target = parse_qs(parsed.query).get("uddg", [""])[0]
            return unquote(target)
        if url.startswith("//duckduckgo.com/l/"):
            target = parse_qs(urlparse(f"https:{url}").query).get("uddg", [""])[0]
            return unquote(target)
        return url if url.startswith(("http://", "https://")) else ""

    def _clean_html(self, value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(value or ""))).strip()

    def _query_variants(self, request: SearchDiscoveryRequest) -> list[str]:
        base = " ".join([request.query, request.location]).strip()
        quoted = f'"{request.query}" "{request.location}"'.strip()
        variants = [
            f"{base} official website",
            f"{base} contact email",
            f"{base} contact us",
            f"{base} email phone",
            f"{quoted} email",
            f"{quoted} contact",
            f"{base} facebook instagram",
        ]
        seen: set[str] = set()
        clean: list[str] = []
        for item in variants:
            normalized = " ".join(item.split())
            if normalized and normalized.lower() not in seen:
                seen.add(normalized.lower())
                clean.append(normalized)
        return clean

    def _offline_discovery(self, request: SearchDiscoveryRequest, degraded: bool = False) -> list[SearchDiscoveryResult]:
        query_slug = "-".join(part for part in request.query.lower().split() if part)
        location_slug = "-".join(part for part in request.location.lower().split() if part)
        examples = [
            f"https://example.com/{location_slug}/{query_slug}",
            f"https://www.google.com/maps/search/{query_slug}+{location_slug}",
        ]
        return [
            SearchDiscoveryResult(
                title=f"{request.query.title()} seed {index}",
                url=url,
                snippet="Offline discovery preview" + (" after DDGS fallback" if degraded else ""),
                engine=request.engines[0] if request.engines else SearchEngine.duckduckgo,
                rank=index,
                candidate=self._candidate_from_result(url, request, request.engines[0] if request.engines else SearchEngine.duckduckgo, index),
            )
            for index, url in enumerate(examples, start=1)
        ]

    def followup_candidates(
        self,
        html: str,
        source_url: str,
        query: str,
        location: str,
        depth: int,
        include_contact_pages: bool = True,
        include_social_profiles: bool = True,
        limit: int = 20,
    ) -> list[URLCandidate]:
        base_host = urlparse(source_url).netloc.lower()
        directory_source = any(domain in base_host for domain in DIRECTORY_DOMAINS)
        rows: list[tuple[str, URLType, float, str]] = []
        seen: set[str] = set()
        for raw in HREF_RE.findall(html or ""):
            href = unescape(raw).strip()
            if not href or href.startswith(("#", "javascript:", "data:", "mailto:", "tel:")):
                continue
            url = urljoin(source_url, href).split("#", 1)[0]
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            lower = url.lower()
            if not parsed.scheme.startswith("http") or not host or url in seen:
                continue
            seen.add(url)
            is_social = any(domain in host for domain in SOCIAL_DOMAINS)
            is_contact = host == base_host and any(marker in lower for marker in CONTACT_MARKERS)
            if is_social and include_social_profiles:
                rows.append((url, URLType.social_profile, 0.82, "social_profile"))
            elif is_contact and include_contact_pages:
                url_type = URLType.website_contact if "contact" in lower or "reach" in lower else URLType.website_about
                rows.append((url, url_type, 0.88, "contact_or_about"))
            elif directory_source and include_contact_pages and host != base_host and not any(domain in host for domain in LOW_VALUE_DOMAINS):
                rows.append((url, URLType.website_homepage, 0.50, "directory_outbound_website"))
        if include_contact_pages and base_host and not any(domain in base_host for domain in SOCIAL_DOMAINS):
            parsed_source = urlparse(source_url)
            root = f"{parsed_source.scheme or 'https'}://{base_host}"
            for path in CONTACT_PATHS:
                url = f"{root}{path}"
                if url not in seen:
                    seen.add(url)
                    url_type = URLType.website_contact if "contact" in path else URLType.website_about
                    rows.append((url, url_type, 0.72, "guessed_contact_path"))
        candidates: list[URLCandidate] = []
        for rank, (url, url_type, priority, reason) in enumerate(rows[:limit], start=1):
            candidates.append(
                URLCandidate(
                    url=url,
                    source=f"page_link:{reason}",
                    depth=depth + 1,
                    priority=max(0.25, priority - rank * 0.01),
                    page_type=url_type.value,
                    url_type=url_type,
                    domain_yield_rate=0.68 if url_type == URLType.website_contact else 0.46,
                    parent_page_yield=0.62,
                    domain_render_required=url_type == URLType.social_profile,
                    js_complexity_score=0.76 if url_type == URLType.social_profile else 0.24,
                    last_extraction_confidence=0.52,
                    metadata={
                        "query": query,
                        "location": location,
                        "parent_url": source_url,
                        "domain": urlparse(url).netloc,
                        "reason": reason,
                    },
                )
            )
        return candidates

    def _candidate_from_result(
        self,
        url: str,
        request: SearchDiscoveryRequest,
        engine: SearchEngine,
        rank: int,
    ) -> URLCandidate:
        parsed = urlparse(url)
        lower = url.lower()
        host = parsed.netloc.lower()
        path = parsed.path.lower()
        if "google.com/maps" in lower:
            url_type = URLType.maps_search_grid
        elif any(domain in host for domain in SOCIAL_DOMAINS):
            url_type = URLType.social_profile
        elif any(marker in path for marker in ["contact", "reach-us", "contact-us"]):
            url_type = URLType.website_contact
        elif "about" in path:
            url_type = URLType.website_about
        elif any(domain in host for domain in DIRECTORY_DOMAINS):
            url_type = URLType.directory_profile
        else:
            url_type = URLType.website_homepage
        priority = max(0.25, 1.0 - (rank * 0.025))
        if url_type == URLType.website_contact:
            priority = min(1.0, priority + 0.18)
        elif url_type == URLType.directory_profile:
            priority = max(0.25, priority - 0.10)
        return URLCandidate(
            url=url,
            source=f"search:{engine.value}",
            depth=0,
            priority=priority,
            page_type=url_type.value,
            url_type=url_type,
            domain_yield_rate=0.76 if url_type == URLType.website_contact else 0.70 if "maps" in lower else 0.52,
            parent_page_yield=0.65,
            domain_render_required=url_type == URLType.social_profile or "maps" in lower,
            js_complexity_score=0.80 if url_type == URLType.social_profile or "maps" in lower else 0.20,
            last_extraction_confidence=0.55,
            metadata={
                "query": request.query,
                "location": request.location,
                "search_engine": engine.value,
                "result_rank": rank,
                "domain": parsed.netloc,
            },
        )

    def _url_key(self, url: str) -> str:
        parsed = urlparse(url)
        host = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.rstrip("/") or "/"
        return f"{host}{path}".lower()

    def _engine_from_source(self, source: str) -> SearchEngine:
        normalized = source.lower()
        for engine in SearchEngine:
            if engine.value in normalized:
                return engine
        return SearchEngine.duckduckgo

    def state(self) -> dict[str, object]:
        return {
            "enabled": self.enable_network_search,
            "package": "ddgs",
            "engines": [engine.value for engine in SearchEngine],
            "network_default": "disabled until operator enables real discovery",
        }
