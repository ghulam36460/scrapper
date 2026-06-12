from __future__ import annotations

import asyncio

from asagus.config import Settings
from asagus.layers.discovery import SearchDiscoveryLayer
from asagus.layers.dom_tools import DOMTools
from asagus.layers.enrichment import EnrichmentLayer
from asagus.layers.external_adapters import external_adapter_state, platform_for_url
from asagus.layers.extraction import ExtractionLayer
from asagus.layers.fetch import FetchLayer
from asagus.layers.lead_intelligence import build_citywide_queries
from asagus.layers.outreach_intelligence import detect_niche, outreach_profile_for
from asagus.layers.social_auth import SocialAuthLayer
from asagus.models import (
    ExtractionMethod,
    FetchMode,
    FetchResult,
    PolicyDecision,
    ScrapeStartRequest,
    SearchDiscoveryRequest,
    ThroughputProfile,
    URLCandidate,
    URLType,
)
from asagus.services.job_helpers import (
    antibot_preset_plan,
    candidate_partial_record,
    effective_runtime_flags,
    effective_website_filter,
    mode_plan,
)


def test_per_job_runtime_flags_can_override_preview_defaults() -> None:
    settings = Settings(enable_network_fetch=False, enable_search_discovery=False)
    request = ScrapeStartRequest(
        query="restaurants",
        location="Lahore",
        enable_network_fetch=True,
        enable_search_discovery=True,
    )

    assert effective_runtime_flags(request, settings) == (True, True)


def test_per_job_runtime_flags_can_disable_enabled_defaults() -> None:
    settings = Settings(enable_network_fetch=True, enable_search_discovery=True)
    request = ScrapeStartRequest(
        query="restaurants",
        location="Lahore",
        enable_network_fetch=False,
        enable_search_discovery=False,
    )

    assert effective_runtime_flags(request, settings) == (False, False)


def test_antibot_presets_resolve_to_active_browser_engines() -> None:
    settings = Settings(browser_automation_engine="playwright")

    assert antibot_preset_plan(
        ScrapeStartRequest(query="cafes", location="Lahore", antibot_preset="high-stealth"),
        settings,
    )["browser_engine"] == "camoufox"
    assert antibot_preset_plan(
        ScrapeStartRequest(query="cafes", location="Lahore", antibot_preset="balanced"),
        settings,
    )["browser_engine"] == "patchright"
    assert antibot_preset_plan(
        ScrapeStartRequest(query="cafes", location="Lahore", antibot_preset="high-speed"),
        settings,
    )["browser_engine"] == "playwright"


def test_operator_browser_engine_override_is_explicit() -> None:
    settings = Settings(browser_automation_engine="auto")
    plan = antibot_preset_plan(
        ScrapeStartRequest(query="clinics", location="Lahore", antibot_preset="high-speed"),
        settings,
    )

    assert plan["browser_engine"] == "auto"
    assert plan["operator_engine_override"] == "auto"


def test_mode_plan_carries_research_safety_metadata() -> None:
    profile = ThroughputProfile(
        io_concurrency=2,
        cpu_workers=1,
        browser_contexts=1,
        queue_maxsize=100,
        backpressure_policy="defer_low_priority",
    )
    request = ScrapeStartRequest(query="clinics", location="Lahore", antibot_preset="balanced")
    plan = antibot_preset_plan(request, Settings())
    resolved = mode_plan(request, profile, plan)

    assert resolved["antibot_preset"]["browser_engine"] == "patchright"
    assert resolved["safety"]["challenge_bypass"] is False
    assert resolved["safety"]["scope"] == "educational_research"


def test_social_auth_layer_uses_selected_saved_session_only(tmp_path) -> None:
    facebook_state = tmp_path / "default" / "facebook.storage_state.json"
    facebook_state.parent.mkdir(parents=True)
    facebook_state.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
    settings = Settings(social_auth_sessions_dir=str(tmp_path))
    request = ScrapeStartRequest(
        query="restaurants",
        location="Lahore",
        social_auth_mode="authenticated",
        social_auth_platforms=["facebook"],
        social_auth_session_label="default",
    )
    layer = SocialAuthLayer(settings, request)

    facebook = layer.resolve("https://www.facebook.com/sample-page")
    instagram = layer.resolve("https://www.instagram.com/sample-page")
    website = layer.resolve("https://example.com/sample-page")

    assert facebook.enabled is True
    assert facebook.session_available is True
    assert facebook.storage_state_path == str(facebook_state)
    assert instagram.enabled is False
    assert instagram.reason == "platform_not_selected"
    assert website.enabled is False


def test_social_auth_required_missing_session_fails_before_browser(tmp_path) -> None:
    settings = Settings(social_auth_sessions_dir=str(tmp_path))
    request = ScrapeStartRequest(
        query="restaurants",
        location="Lahore",
        social_auth_mode="authenticated",
        social_auth_platforms=["instagram"],
        social_auth_required=True,
    )
    fetcher = FetchLayer(enable_network_fetch=True, social_auth_layer=SocialAuthLayer(settings, request))
    candidate = URLCandidate(url="https://www.instagram.com/sample-page", url_type=URLType.social_profile)
    decision = PolicyDecision(
        decision="crawl",
        fetch_mode=FetchMode.dynamic,
        extraction_method=ExtractionMethod.css,
    )

    result = asyncio.run(fetcher.fetch(candidate, decision))

    assert result.error == "social_auth_session_missing:instagram"
    assert result.fetch_mode == FetchMode.dynamic


def test_mode_plan_carries_social_auth_isolation_metadata() -> None:
    profile = ThroughputProfile(io_concurrency=2, cpu_workers=1, browser_contexts=1, queue_maxsize=100)
    request = ScrapeStartRequest(
        query="clinics",
        location="Lahore",
        social_auth_mode="authenticated",
        social_auth_platforms=["facebook", "instagram"],
        social_auth_session_label="outreach",
        social_auth_required=True,
    )

    resolved = mode_plan(request, profile, antibot_preset_plan(request, Settings()))

    assert resolved["social_auth"]["mode"] == "authenticated"
    assert resolved["social_auth"]["platforms"] == ["facebook", "instagram"]
    assert resolved["social_auth"]["session_label"] == "outreach"
    assert resolved["social_auth"]["required"] is True
    assert resolved["social_auth"]["session_isolation"] == "platform_scoped_browser_context"


def test_aws_waf_javascript_page_is_manual_review_challenge() -> None:
    html = """
    <html>
      <head><title>JavaScript is disabled</title></head>
      <body>
        <h1>JavaScript is disabled</h1>
        <script>window.awsWafIntegration = { saveReferrer: true };</script>
      </body>
    </html>
    """

    challenge = DOMTools().detect_challenge(html, status_code=202)

    assert challenge["challenge_detected"] is True
    assert challenge["manual_review_required"] is True
    assert "awswaf" in challenge["signals"]
    assert challenge["bypass_attempted"] is False


def test_social_only_implies_no_owned_website_filter() -> None:
    request = ScrapeStartRequest(query="restaurants", location="Qatar", discovery_mode="social_only")

    assert effective_website_filter(request) == "no_website"


def test_social_only_discovery_includes_maps_and_social_platforms() -> None:
    layer = SearchDiscoveryLayer(enable_network_search=False)
    results = asyncio.run(
        layer.discover(
            SearchDiscoveryRequest(
                query="restaurants",
                location="Qatar",
                max_results=12,
                discovery_mode="social_only",
                website_filter="no_website",
            )
        )
    )

    urls = [row.url for row in results]
    assert any("facebook.com" in url for url in urls)
    assert any("instagram.com" in url for url in urls)
    assert any("google.com/maps" in url for url in urls)


def test_social_candidate_can_be_kept_as_partial_no_website_lead() -> None:
    request = ScrapeStartRequest(query="restaurants", location="Qatar", discovery_mode="social_only")
    candidate = URLCandidate(
        url="https://www.facebook.com/local-restaurant-qatar",
        source="search:duckduckgo",
        url_type=URLType.social_profile,
        page_type=URLType.social_profile.value,
    )

    record = candidate_partial_record(candidate, request, "test")

    assert record is not None
    assert record.website_url == ""
    assert record.facebook_url == candidate.url
    assert record.category == "restaurants"


def test_citywide_query_builder_expands_location_coverage() -> None:
    queries = build_citywide_queries("dentists", "Austin, TX, USA", max_queries=12)

    assert len(queries) >= 8
    assert any("Downtown Austin" in query for query in queries)
    assert any("within 5 km" in query for query in queries)
    assert any("United States" in query for query in queries)


def test_extraction_merges_downloaded_tool_lead_intelligence_patterns() -> None:
    html = """
    <html>
      <head>
        <title>Bright Smile Clinic</title>
        <script type="application/ld+json">
        {"@type":"LocalBusiness","name":"Bright Smile Clinic","telephone":"+1 512 555 0100","aggregateRating":{"ratingValue":"4.7","reviewCount":"128"}}
        </script>
      </head>
      <body>
        <a href="https://api.whatsapp.com/send?phone=15125550100">WhatsApp</a>
        <a href="https://instagram.com/brightsmileatx">Instagram</a>
        <script src="https://www.google-analytics.com/analytics.js"></script>
        <script>window.tidioChatApi = true;</script>
      </body>
    </html>
    """
    fetch = FetchResult(url="https://brightsmile.example", html=html, markdown=html, fetch_mode=FetchMode.static)

    record = ExtractionLayer()._extract_css_xpath(fetch)

    assert record.name == "Bright Smile Clinic"
    assert record.phone == "+1 512 555 0100"
    assert record.whatsapp == "+15125550100"
    assert record.instagram_url == "https://www.instagram.com/brightsmileatx"
    assert record.rating == 4.7
    assert record.review_count == 128
    assert record.raw_fields["has_chatbot"] is True
    assert record.raw_fields["has_google_analytics"] is True


def test_enrichment_adds_whatsapp_ready_link_metadata() -> None:
    record = ExtractionLayer()._extract_css_xpath(
        FetchResult(
            url="https://example.com",
            html="<html><body><h1>Sample Business</h1><a href='tel:+923001234567'>Call</a></body></html>",
            fetch_mode=FetchMode.static,
        )
    )

    enriched = asyncio.run(EnrichmentLayer().enrich(record, default_city="Lahore"))

    assert enriched.phone == "+923001234567"
    assert enriched.whatsapp == "+923001234567"
    assert enriched.whatsapp_valid is True
    assert enriched.raw_fields["wa_link"] == "https://wa.me/923001234567"
    assert enriched.raw_fields["whatsapp_status"] == "candidate_from_phone"


def test_outreach_profile_scores_no_website_service_leads() -> None:
    profile = outreach_profile_for(
        {
            "name": "Austin Emergency Plumbing",
            "category": "plumber",
            "phone": "+15125550100",
            "whatsapp": "+15125550100",
            "city": "Austin",
            "website_url": "",
            "review_count": 86,
            "confidence": 0.82,
            "raw_fields": {"decision_makers": [{"name": "Maya Patel", "title": "Owner"}]},
        }
    )

    assert profile["score"] >= 75
    assert profile["segment"] == "high"
    assert profile["niche"] == "plumbing"
    assert profile["recommended_channel"] == "whatsapp"
    assert "no_owned_website_opportunity" in profile["reasons"]


def test_enrichment_persists_outreach_profile_metadata() -> None:
    extracted = ExtractionLayer()._extract_css_xpath(
        FetchResult(
            url="https://maps.google.com/maps/place/sample",
            html="<html><body><h1>Bright Dental Clinic</h1><a href='tel:+15125550100'>Call</a></body></html>",
            fetch_mode=FetchMode.static,
        )
    )
    extracted = extracted.model_copy(update={"website_url": "", "city": "Austin", "category": "dentist", "review_count": 128})

    enriched = asyncio.run(EnrichmentLayer().enrich(extracted, default_city="Austin"))

    assert enriched.raw_fields["outreach_fit_score"] >= 75
    assert enriched.raw_fields["outreach_segment"] == "high"
    assert enriched.raw_fields["outreach_profile"]["recommended_channel"] in {"whatsapp", "phone"}


def test_detect_niche_uses_local_service_terms() -> None:
    assert detect_niche("Premium Auto Garage", "vehicle service") == "auto_repair"
    assert detect_niche("Smile Studio", "dental clinic") == "dental"


def test_external_adapter_state_reports_downloaded_and_installed_integrations() -> None:
    state = external_adapter_state()

    assert state["adapters"]["scrapy"]["available"] is True
    assert state["adapters"]["scrapling"]["available"] is True
    assert state["adapters"]["agent_reach"]["status"] in {"ok", "source_available_not_installed"}
    assert "platform_channels" in state
    assert state["integration_style"] == "native_glue_and_optional_adapters"


def test_agent_reach_style_platform_router_identifies_supported_channels() -> None:
    assert platform_for_url("https://www.youtube.com/watch?v=abc") == "youtube"
    assert platform_for_url("https://example.com/feed.xml") == "rss"
    assert platform_for_url("https://github.com/asagus/scraper") == "github"
    assert platform_for_url("https://example.com/contact") == "web"


def test_extraction_uses_scrapy_and_scrapling_selector_adapters() -> None:
    html = """
    <html>
      <head>
        <meta property="og:url" content="https://selectordental.example/" />
      </head>
      <body>
        <section itemscope itemtype="https://schema.org/LocalBusiness">
          <meta itemprop="name" content="Selector Dental Studio" />
          <a itemprop="telephone" href="tel:+15551234567">Call us</a>
          <a itemprop="email" href="mailto:hello@selectordental.example">Email</a>
          <span itemprop="address">9 Market Street, Austin</span>
        </section>
        <a href="/team">Team</a>
      </body>
    </html>
    """
    record = ExtractionLayer()._extract_css_xpath(
        FetchResult(url="https://selectordental.example", html=html, markdown=html, fetch_mode=FetchMode.static)
    )

    assert record.name == "Selector Dental Studio"
    assert record.phone == "+15551234567"
    assert record.email == "hello@selectordental.example"
    assert record.address == "9 Market Street, Austin"
    assert record.raw_fields["scrapy_selector_fields"]["adapter"] in {"scrapy.Selector", "parsel.Selector"}
    assert record.raw_fields["scrapling_parser_fields"]["adapter"].startswith("scrapling.")


def test_followup_candidates_include_outreach_contact_paths() -> None:
    candidates = SearchDiscoveryLayer(enable_network_search=False).followup_candidates(
        html="<html><body></body></html>",
        source_url="https://example.com",
        query="clinics",
        location="Austin",
        depth=0,
        limit=20,
    )
    urls = {candidate.url for candidate in candidates}

    assert "https://example.com/team" in urls
    assert "https://example.com/support" in urls
    assert "https://example.com/impressum" in urls
