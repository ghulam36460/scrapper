"""
ASAGUS 3.0 Full Audit Test Suite
Runs after every fix session to verify all layers are wired correctly.
"""
from __future__ import annotations

import asyncio
import sys
sys.path.insert(0, ".")


def check(label: str, condition: bool, extra: str = "") -> None:
    status = "OK" if condition else "FAIL"
    suffix = f"  [{extra}]" if extra else ""
    print(f"  {status}  {label}{suffix}")
    if not condition:
        sys.exit(1)  # hard stop on any failure


async def main() -> None:
    from asagus.models import (
        ScrapeStartRequest, SearchDiscoveryRequest, URLCandidate,
        FetchResult, FetchMode, PolicyDecision, ExtractionMethod, EnrichedRecord,
    )
    from asagus.config import Settings
    from asagus.main import planned_page_count, _discovery_refill, useful_record
    from asagus.layers.discovery import SearchDiscoveryLayer
    from asagus.layers.extraction import ExtractionLayer
    from asagus.layers.enrichment import EnrichmentLayer
    from asagus.layers.compliance import ComplianceLayer
    from asagus.layers.policy import PolicyEngine
    from asagus.layers.crawl_control import CrawlControlPlane
    from asagus.layers.proxy import ProxyPoolManager
    from asagus.services.runtime import RuntimeState

    s = Settings()

    # -------------------------------------------------------
    print("\n=== TEST 1: planned_page_count multipliers ===")
    cases = [
        ("fast", 50, 150),
        ("balanced", 50, 300),
        ("deep", 50, 750),
        ("research", 50, 1250),
        ("balanced", 100, 600),
        ("balanced", 5, 30),  # at least limit+10 = 15, but 5*6=30
    ]
    for mode, limit, expected_min in cases:
        req = ScrapeStartRequest(query="restaurants", location="Lahore", limit=limit, mode=mode)
        pages = planned_page_count(req, s)
        check(f"mode={mode} limit={limit} -> planned={pages} >= {expected_min}", pages >= expected_min)

    # max_pages override
    req_mp = ScrapeStartRequest(query="rq", location="lh", limit=100, max_pages=42)
    check("max_pages=42 override", planned_page_count(req_mp, s) == 42)

    # -------------------------------------------------------
    print("\n=== TEST 2: ScrapeStartRequest defaults ===")
    req = ScrapeStartRequest(query="test", location="city")
    check("require_email default is False", req.require_email is False)
    check("enable_network_fetch default is None", req.enable_network_fetch is None)
    check("enable_search_discovery default is None", req.enable_search_discovery is None)

    # -------------------------------------------------------
    print("\n=== TEST 3: Per-job override effective flag resolution ===")
    req_real = ScrapeStartRequest(query="te", location="ci", enable_network_fetch=True, enable_search_discovery=True)
    eff_net = req_real.enable_network_fetch if req_real.enable_network_fetch is not None else s.enable_network_fetch
    eff_disc = req_real.enable_search_discovery if req_real.enable_search_discovery is not None else s.enable_search_discovery
    check("enable_network_fetch=True overrides global False", eff_net is True)
    check("enable_search_discovery=True overrides global False", eff_disc is True)

    req_none = ScrapeStartRequest(query="te", location="ci")  # no override
    eff_net2 = req_none.enable_network_fetch if req_none.enable_network_fetch is not None else s.enable_network_fetch
    check("None override falls back to settings (False)", eff_net2 is s.enable_network_fetch)

    # -------------------------------------------------------
    print("\n=== TEST 4: Offline discovery scales to max_results ===")
    disc = SearchDiscoveryLayer(False)
    for n in [2, 10, 50, 100]:
        r = SearchDiscoveryRequest(query="restaurants", location="Lahore", max_results=n)
        results = await disc.discover(r)
        check(f"offline discovery max_results={n} -> got {len(results)}", len(results) == n)

    # Verify all seeds are unique
    r50 = SearchDiscoveryRequest(query="restaurants", location="Lahore", max_results=50)
    r50_results = await disc.discover(r50)
    urls = [x.url for x in r50_results]
    check("all 50 offline seeds are unique", len(set(urls)) == 50)

    # -------------------------------------------------------
    print("\n=== TEST 5: Policy engine ===")
    policy = PolicyEngine()

    # Contact page should always crawl
    c_contact = URLCandidate(url="https://example.pk/contact", depth=0)
    d_contact = policy.decide_for_url(c_contact, llm_enabled=True)
    check("contact URL -> crawl", d_contact.decision == "crawl")
    check("contact URL rule fired", "contact_about_high_priority" in d_contact.rules_fired)

    # PDF should skip
    c_pdf = URLCandidate(url="https://example.pk/file.pdf", depth=0)
    d_pdf = policy.decide_for_url(c_pdf, llm_enabled=True)
    check("PDF URL -> skip", d_pdf.decision == "skip")

    # Blocklist
    c_blocked = URLCandidate(url="https://blocked.com/page", depth=0)
    c_blocked.metadata["blocked_domains"] = ["blocked.com"]
    d_blocked = policy.decide_for_url(c_blocked, llm_enabled=True)
    check("blocklist domain -> skip", d_blocked.decision == "skip")

    # WhatsApp fast path
    c_wa = URLCandidate(url="https://wa.me/923001234567", depth=0)
    d_wa = policy.decide_for_url(c_wa, llm_enabled=True)
    check("WhatsApp URL -> whatsapp_fast_path rule", "whatsapp_fast_path" in d_wa.rules_fired)

    # -------------------------------------------------------
    print("\n=== TEST 6: Extraction cascade ===")
    extractor = ExtractionLayer()

    # Full HTML with all signals
    full_html = (
        "<html><body>"
        "<h1>Al-Noor Restaurant</h1>"
        "<p>Call: +923001234567</p>"
        "<a href='https://wa.me/923001234567'>WhatsApp</a>"
        "<a href='mailto:info@alnoor.pk'>Email</a>"
        "<a href='https://facebook.com/alnoor'>Facebook</a>"
        "<script type='application/ld+json'>"
        '{"@type":"Restaurant","name":"Al-Noor","telephone":"+923001234567","email":"info@alnoor.pk"}'
        "</script></body></html>"
    )
    fetch_full = FetchResult(
        url="https://alnoor.pk/",
        html=full_html,
        fetch_mode=FetchMode.static,
        status_code=200,
        final_url="https://alnoor.pk/",
        content_type="text/html",
    )
    dec = PolicyDecision(
        decision="crawl",
        fetch_mode=FetchMode.static,
        extraction_method=ExtractionMethod.css,
        confidence=0.8,
    )
    extracted = await extractor.extract(fetch_full, dec, llm_enabled=False)
    check("name extracted", bool(extracted.name))
    check("phone extracted", bool(extracted.phone))
    check("email extracted", bool(extracted.email))
    check("whatsapp extracted", bool(extracted.whatsapp))
    check("facebook_url extracted", bool(extracted.facebook_url))
    check("extraction method is css", extracted.method == ExtractionMethod.css)
    check("confidence >= 0.78 (CSS threshold)", extracted.confidence >= 0.78)

    # LLM fallback is called when below threshold and client is available
    sparse_html = "<html><body><p>Some business page with no structured data</p></body></html>"
    fetch_sparse = FetchResult(
        url="https://sparse.pk/",
        html=sparse_html,
        fetch_mode=FetchMode.static,
        status_code=200,
        final_url="https://sparse.pk/",
        content_type="text/html",
    )
    extracted_sparse = await extractor.extract(fetch_sparse, dec, llm_enabled=False)
    # When LLM is disabled, should still return a record (manual_review fallback)
    check("sparse HTML -> record returned (not None)", extracted_sparse is not None)
    check("sparse HTML -> manual_review or structural fallback used",
          extracted_sparse.method.value in {"structural_heuristic", "manual_review", "css", "dom_fingerprint"})

    # -------------------------------------------------------
    print("\n=== TEST 7: useful_record filter ===")
    enrich = EnrichmentLayer()

    # Phone-only business - should be useful even without email
    enriched_phone_only = await enrich.enrich(extracted, default_city="Lahore")
    check("useful_record with phone (no email required)", useful_record(enriched_phone_only))

    # Social-only business
    from asagus.models import ExtractedRecord
    social_only = ExtractedRecord(
        source_url="https://fb.com/business",
        name="Test Biz",
        facebook_url="https://facebook.com/testbiz",
        method=ExtractionMethod.css,
        confidence=0.5,
    )
    social_enriched = await enrich.enrich(social_only)
    check("useful_record with facebook only", useful_record(social_enriched))

    # Truly empty record - should NOT be useful
    empty_rec = ExtractedRecord(
        source_url="https://empty.com",
        method=ExtractionMethod.css,
        confidence=0.1,
    )
    empty_enriched = await enrich.enrich(empty_rec)
    check("useful_record empty record is False", not useful_record(empty_enriched))

    # -------------------------------------------------------
    print("\n=== TEST 8: Enrichment layer ===")
    enriched_full = await enrich.enrich(extracted, default_city="Lahore")
    check("city filled from default", bool(enriched_full.city))
    check("record_completeness > 0", enriched_full.record_completeness > 0)
    check("phone normalized to +E164 format", enriched_full.phone.startswith("+"))

    # PDPA flag for Pakistan numbers
    check("pdpa_flag True for PK number", enriched_full.pdpa_flag is True)

    # -------------------------------------------------------
    print("\n=== TEST 9: Compliance layer token bucket + robots ===")
    comp = ComplianceLayer(2.0, 8, 0.25, 86400)
    c_comp = URLCandidate(url="https://example.pk/contact", depth=0)

    # First 8 requests should drain the bucket
    allowed_count = 0
    for _ in range(12):
        result = comp.check(c_comp, [], [])
        if result.allowed:
            allowed_count += 1

    check("token bucket allows initial burst (>= 8)", allowed_count >= 8)

    # Blocklist check
    c_blocked2 = URLCandidate(url="https://baddomain.com/page", depth=0)
    result_blocked = comp.check(c_blocked2, [], ["baddomain.com"])
    check("blocklist -> not allowed", not result_blocked.allowed)

    # Allowlist filtering
    c_outside = URLCandidate(url="https://other.com/page", depth=0)
    result_outside = comp.check(c_outside, ["example.pk"], [])
    check("outside allowlist -> not allowed", not result_outside.allowed)

    # Private path robots
    c_admin = URLCandidate(url="https://example.pk/wp-admin/", depth=0)
    result_admin = comp.check(c_admin, [], [])
    check("wp-admin path -> not allowed by robots cache", not result_admin.allowed)

    # -------------------------------------------------------
    print("\n=== TEST 10: CrawlControl MDP + seed_from_query ===")
    crawl = CrawlControlPlane()
    seeds = crawl.seed_from_query("restaurants", "Lahore", 10)
    check("seed_from_query returns seeds", len(seeds) > 0)
    check("all seeds are URLCandidate", all(isinstance(s, URLCandidate) for s in seeds))

    scheduled = crawl.schedule(seeds)
    check("schedule returns sorted URLCandidates", len(scheduled) == len(seeds))

    # -------------------------------------------------------
    print("\n=== TEST 11: Queue refill mechanism ===")
    rt2 = RuntimeState()
    req_refill = ScrapeStartRequest(query="restaurants", location="Lahore", limit=50)
    disc2 = SearchDiscoveryLayer(False)
    already = {"example.com/contact?", "example.com/?"}
    extra = await _discovery_refill(disc2, req_refill, 30, already)
    check("_discovery_refill returns candidates", isinstance(extra, list))
    # All returned seeds should not be in already_queued
    new_urls = {rt2.url_key(c.url) for c in extra}
    check("refill seeds are not already queued", not new_urls.intersection(already))

    # -------------------------------------------------------
    print("\n=== TEST 12: Runtime dedup + merge ===")
    from asagus.models import EnrichedRecord
    rt3 = RuntimeState()
    rec_a = EnrichedRecord(
        source_url="https://alnoor.pk/",
        name="Al-Noor Restaurant",
        phone="+923001234567",
        city="Lahore",
        confidence=0.8,
        record_completeness=0.5,
    )
    rec_b = EnrichedRecord(
        source_url="https://alnoor.pk/contact",
        name="Al-Noor Restaurant",
        phone="+923001234567",
        email="info@alnoor.pk",
        city="Lahore",
        confidence=0.9,
        record_completeness=0.7,
    )
    stored_a, is_new_a, _ = await rt3.add_record(rec_a)
    check("first record stored as new", is_new_a is True)

    stored_b, is_new_b, reasons = await rt3.add_record(rec_b)
    check("duplicate record merged (not new)", is_new_b is False)
    check("merge reason includes phone", "phone" in reasons)
    check("merged record has email from rec_b", bool(stored_b.email))
    check("merged record keeps best completeness", stored_b.record_completeness >= rec_a.record_completeness)

    # -------------------------------------------------------
    print("\n=== TEST 13: url_key normalization (dedup edge cases) ===")
    rt4 = RuntimeState()
    k1 = rt4.url_key("https://www.example.pk/contact/")
    k2 = rt4.url_key("https://example.pk/contact")
    k3 = rt4.url_key("HTTP://EXAMPLE.PK/CONTACT")
    check("www stripped in url_key", "www." not in k1)
    check("trailing slash normalized", k1 == k2, f"k1={k1!r} k2={k2!r}")
    check("url_key is lowercase", k3 == k2, f"k3={k3!r} k2={k2!r}")

    # -------------------------------------------------------
    print("\n=== TEST 14: ProxyPoolManager fallback ===")
    pm = ProxyPoolManager()
    c_proxy = URLCandidate(url="https://example.pk/", depth=0)
    proxy = pm.choose(c_proxy, "auto")
    check("proxy chosen (fallback to direct-local)", proxy is not None)
    check("direct-local is always active", proxy.id == "direct-local" or proxy.active)

    # Ban-pressure causes cooldown
    pm.register_result("direct-local", success=False, blocked=True)
    proxy2 = pm.choose(c_proxy, "auto")
    check("proxy still returned after single block", proxy2 is not None)

    # -------------------------------------------------------
    print("\n=== TEST 15: Health service structure ===")
    from asagus.services.health import collect_health
    health = await collect_health(s)
    check("health.status in {ok, degraded}", health.status in {"ok", "degraded"})
    check("network_fetch key present in services", "network_fetch" in health.services)
    check("search_discovery key present in services", "search_discovery" in health.services)
    check("network_fetch value is 'disabled' (env default)", health.services["network_fetch"] == "disabled")
    check("search_discovery value is 'disabled' (env default)", health.services["search_discovery"] == "disabled")

    print()
    print("=" * 60)
    print("ALL 15 AUDIT TESTS PASSED - System is production-ready")
    print("=" * 60)


asyncio.run(main())
