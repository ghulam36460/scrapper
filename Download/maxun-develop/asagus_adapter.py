"""
ASAGUS Adapter for Maxun — visual no-code scraper (Node.js platform).

Maxun is a full Node.js + Postgres + Redis web platform for building visual
"robots" (recorded scraping workflows). It cannot batch-scrape an arbitrary
query headlessly without a pre-recorded robot and a running server, so this
adapter integrates it SAFELY:

  * If Maxun is fully provisioned (node_modules built, MAXUN_API_URL set, and a
    robot mapped for this job), it triggers that robot via Maxun's API and
    collects the run output into the unified CSV.
  * Otherwise it SKIPS gracefully (never blocks the parallel pipeline) and
    reports exactly what is missing, so it can be enabled later without code
    changes.

This keeps Maxun integrated as an optional parallel worker without faking data.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))
from unified_tool_adapter import UnifiedToolAdapter  # noqa: E402

_THIS_DIR = Path(__file__).resolve().parent

# Mode -> number of rendered pages to extract from (Maxun specializes in
# JS-rendered pages, so it uses a real browser via Playwright).
_MODE_URL_BUDGET: dict[str, int] = {
    "fast": 3, "focused": 3, "balanced": 5,
    "deep": 8, "research": 8, "comprehensive": 10,
    "deep_agent": 12, "adaptive": 12, "parallel": 12, "max": 15,
}

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?:\+\d{1,4}[\s().-]?)?(?:\(?\d{2,4}\)?[\s().-]?){2,5}\d{2,4}")
_WA_RE = re.compile(r"(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\+?\d[\d\s().-]{6,})", re.I)
_SKIP_DOMAINS = (
    "google.", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "youtube.com", "linkedin.com", "tripadvisor.", "yelp.", "wikipedia.org",
    "amazon.", "ebay.", "duckduckgo.com",
)


def _clean_phone(raw: str) -> str:
    cleaned = re.sub(r"\s+", " ", raw).strip(" .,-()")
    # Reject ISO date-like patterns (e.g. 2021-08-16, 2013/08/06).
    if re.fullmatch(r"(?:19|20)\d{2}[-/.]\d{1,2}[-/.]\d{1,2}", cleaned):
        return ""
    digits = re.sub(r"\D", "", raw)
    if 7 <= len(digits) <= 15 and len(set(digits)) >= 3 and not digits.startswith(("000", "123456")):
        # A real phone usually has a +, separator, or is a long unbroken run.
        if "+" in raw or any(c in raw for c in "()- ") or len(digits) >= 9:
            return cleaned
    return ""


def _is_business_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return bool(host) and not any(s in host for s in _SKIP_DOMAINS)


def _ddg_seed_urls(query: str, location: str, max_results: int) -> list[str]:
    """Resilient multi-engine seed discovery (DDG -> Bing), no API key."""
    import random
    import time as _time
    from urllib.parse import quote_plus

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

    for _attempt in range(3):
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


class MaxunAdapter(UnifiedToolAdapter):
    """Optional Maxun worker; runs a mapped robot via API or skips cleanly."""

    def _node_available(self) -> bool:
        try:
            return subprocess.run(["node", "--version"], capture_output=True, timeout=5).returncode == 0
        except Exception:
            return False

    def _node_modules_built(self) -> bool:
        return (_THIS_DIR / "node_modules").exists()

    def _api_config(self) -> dict[str, str]:
        return {
            "api_url": os.environ.get("MAXUN_API_URL", ""),
            "api_key": os.environ.get("MAXUN_API_KEY", ""),
            # Optional mapping from ASAGUS query -> Maxun robot id.
            "robot_id": os.environ.get("MAXUN_ROBOT_ID", ""),
        }

    def run(self) -> dict[str, Any]:
        context = self.get_job_context()
        node_ok = self._node_available()
        built = self._node_modules_built()
        api = self._api_config()

        readiness = {
            "node_available": node_ok,
            "node_modules_built": built,
            "api_url_set": bool(api["api_url"]),
            "robot_mapped": bool(api["robot_id"]),
        }

        # Path 1: trigger a mapped robot via Maxun's API (true integration).
        if self.real_run and api["api_url"] and api["robot_id"]:
            try:
                records = self._run_via_api(api)
                for row in records:
                    row.setdefault("source_tool", self.tool_id)
                if records:
                    self.save_records_csv(records)
                data = {
                    "tool_id": self.tool_id,
                    "status": "completed" if records else "no_records",
                    "mode": self.mode,
                    "records": len(records),
                    "output_csv": str(self.csv_path) if records else "",
                    "readiness": readiness,
                    "job_context": context,
                }
                self.save_metadata_json(data)
                return data
            except Exception as exc:
                data = {
                    "tool_id": self.tool_id,
                    "status": "failed",
                    "error": str(exc)[:300],
                    "readiness": readiness,
                    "job_context": context,
                }
                self.save_metadata_json(data)
                return data

        # Path 2: self-contained rendered-page extraction (no server needed).
        # Maxun's specialty is JS-rendered pages, so this fallback uses a real
        # browser (Playwright) to render each seed and extract contact data.
        if self.real_run:
            try:
                records = self._run_via_playwright()
                if records:
                    for row in records:
                        row.setdefault("source_tool", self.tool_id)
                    self.save_records_csv(records)
                    data = {
                        "tool_id": self.tool_id,
                        "status": "completed",
                        "mode": self.mode,
                        "engine": "playwright_self_contained",
                        "records": len(records),
                        "output_csv": str(self.csv_path),
                        "readiness": readiness,
                        "job_context": context,
                    }
                    self.save_metadata_json(data)
                    return data
            except Exception as exc:
                readiness["playwright_error"] = str(exc)[:300]

        # Path 3: graceful skip — explain exactly what is missing.
        missing = []
        if not node_ok:
            missing.append("node")
        if not built:
            missing.append("node_modules (run npm install in maxun-develop)")
        if not api["api_url"]:
            missing.append("MAXUN_API_URL")
        if not api["robot_id"]:
            missing.append("MAXUN_ROBOT_ID (map a recorded robot for this job)")
        data = {
            "tool_id": self.tool_id,
            "status": "no_records" if self.real_run else "skipped_not_provisioned",
            "message": (
                "Maxun ran self-contained but found no records."
                if self.real_run else
                "Maxun is optional and not provisioned for batch runs; skipped."
            ),
            "missing": missing,
            "readiness": readiness,
            "job_context": context,
        }
        self.save_metadata_json(data)
        return data

    def _run_via_playwright(self) -> list[dict[str, Any]]:
        """Render seed pages with a real browser and extract contact data."""
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # playwright not installed
            raise RuntimeError(f"playwright unavailable: {exc}") from exc

        budget = min(_MODE_URL_BUDGET.get(self.mode, 5), max(self.limit, 3))
        seeds = _ddg_seed_urls(self.query, self.location, budget)
        if not seeds:
            return []

        records: list[dict[str, Any]] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    )
                )
                for url in seeds:
                    try:
                        page.goto(url, timeout=30000, wait_until="domcontentloaded")
                        html = page.content()
                        title = page.title()
                    except Exception:
                        continue
                    rec = self._extract(html, title, url)
                    if rec:
                        records.append(rec)
            finally:
                browser.close()
        return records

    def _extract(self, html: str, title: str, url: str) -> dict[str, Any] | None:
        text = re.sub(r"<[^>]+>", " ", html)
        host = urlparse(url).netloc.lower().removeprefix("www.")
        name = (title.split("|")[0].split("-")[0].strip()
                or host.split(".")[0].replace("-", " ").title())
        emails = [e.lower() for e in _EMAIL_RE.findall(text)
                  if not e.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))
                  and not any(b in e.lower() for b in ("example.", "sentry.", "wixpress.", "schema.org"))]
        phones = [p for p in (_clean_phone(m.group(0)) for m in _PHONE_RE.finditer(text)) if p]
        wa = [m.group(1).strip() for m in _WA_RE.finditer(html)]

        def _social(domain: str) -> str:
            m = re.search(rf'href=["\'](https?://[^"\']*{re.escape(domain)}[^"\']*)["\']', html, re.I)
            return m.group(1).split("?")[0] if m else ""

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

    def _run_via_api(self, api: dict[str, str]) -> list[dict[str, Any]]:
        import requests

        headers = {"Content-Type": "application/json"}
        if api["api_key"]:
            headers["Authorization"] = f"Bearer {api['api_key']}"
        base = api["api_url"].rstrip("/")
        # Maxun exposes a run endpoint per robot; collect rows from the response.
        resp = requests.post(
            f"{base}/api/robots/{api['robot_id']}/run",
            headers=headers,
            json={
                "query": self.query,
                "location": self.location,
                "limit": self.limit,
            },
            timeout=240,
        )
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("data") or payload.get("results") or payload.get("rows") or []
        return [r for r in rows if isinstance(r, dict)]


def main() -> None:
    print(json.dumps(MaxunAdapter().run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
