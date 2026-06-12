from __future__ import annotations

from typing import Any

from asagus.models import CapabilityCard


def capability_catalog() -> list[dict[str, Any]]:
    cards = [
        CapabilityCard(key="inverted_index", name="Inverted Index", category="retrieval", status="implemented", practical_use="Fast term postings for candidate generation", source_module="layers.search_index"),
        CapabilityCard(key="tfidf", name="TF-IDF", category="retrieval", status="implemented", practical_use="Interpretable lexical ranking", source_module="layers.search_index"),
        CapabilityCard(key="ann", name="ANN Search", category="retrieval", status="implemented", practical_use="Local LSH buckets; Qdrant HNSW in production", source_module="layers.search_index"),
        CapabilityCard(key="bm25_ltr_hybrid", name="BM25 + LTR + Hybrid Retrieval", category="retrieval", status="implemented", practical_use="RRF fused ranking over lexical, dense, sparse, graph and neural-style signals", source_module="layers.retrieval"),
        CapabilityCard(key="bert_transformer_rag", name="BERT / Transformer / RAG Adapters", category="neural", status="adapter_ready", practical_use="Provider-backed embeddings, reranking, extraction and summaries", source_module="layers.nlp_intelligence"),
        CapabilityCard(key="rlhf_feedback", name="RLHF Feedback Loop", category="neural", status="adapter_ready", practical_use="Operator feedback updates crawl/rank rewards", source_module="layers.policy"),
        CapabilityCard(key="self_healing_scrapers", name="Self-Healing Scrapers", category="scraping", status="implemented", practical_use="CSS, XPath, DOM fingerprint, heuristic, LLM and manual review cascade", source_module="layers.extraction"),
        CapabilityCard(key="lead_intelligence", name="Lead Intelligence Fusion", category="scraping", status="implemented", practical_use="Maps-inspired city coverage, WhatsApp links, website tech signals, social profiles and no-website lead metadata", source_module="layers.lead_intelligence"),
        CapabilityCard(key="scrapy_adapter", name="Scrapy Selector Adapter", category="scraping", status="implemented", practical_use="Installed Scrapy/parsel selectors augment extraction with CSS/XPath, itemprop, canonical and contact-link signals", source_module="layers.external_adapters"),
        CapabilityCard(key="scrapling_adapter", name="Scrapling Parser/Fetch Adapter", category="scraping", status="implemented", practical_use="Installed Scrapling parser augments extraction and its static fetcher can recover failed live static fetches", source_module="layers.external_adapters"),
        CapabilityCard(key="firecrawl_adapter", name="Firecrawl Markdown Adapter", category="scraping", status="adapter_ready", practical_use="Optional API/SDK path for LLM-ready markdown scrape/search results", source_module="layers.fetch"),
        CapabilityCard(key="scrapegraph_adapter", name="ScrapeGraphAI Workflow Adapter", category="neural", status="adapter_ready", practical_use="Optional graph-style LLM extraction workflows can be routed after deterministic extraction", source_module="layers.ai_app"),
        CapabilityCard(key="agent_reach_doctor", name="Agent Reach-Style Channel Doctor", category="osint", status="implemented", safety_boundary="Public/authorized platform tooling only; reports availability and does not bypass login or access controls", practical_use="Shows which external platform channels and command-line backends are available for future source adapters", source_module="layers.external_adapters"),
        CapabilityCard(key="dom_css_xpath", name="DOM / CSS / XPath", category="scraping", status="implemented", practical_use="Structured page parsing and selector matching", source_module="layers.dom_tools"),
        CapabilityCard(key="safe_osint", name="Google Dorking / OSINT Fusion", category="osint", status="guarded", safety_boundary="Public business discovery only; blocks credential/session/admin dorks", practical_use="Business source discovery with human review", source_module="layers.osint"),
        CapabilityCard(key="api_sessions", name="API Session Handling", category="osint", status="guarded", safety_boundary="Documented public APIs or owned OAuth only; no exploitation", practical_use="Safe integration with authorized APIs", source_module="layers.osint"),
        CapabilityCard(key="chromium", name="Headless Browser Automation", category="scraping", status="implemented", practical_use="Playwright Chromium rendering behind compliance checks", source_module="layers.browser"),
        CapabilityCard(key="graph", name="Graph / Network Analysis", category="analytics", status="implemented", practical_use="Neo4j-ready competitor, duplicate, same-area and same-network edges", source_module="layers.graph"),
        CapabilityCard(key="vision", name="Computer Vision", category="analytics", status="guarded", safety_boundary="No face identification or biometric recognition", practical_use="Business media labels, OCR adapter, storefront/logo adapter", source_module="layers.vision"),
        CapabilityCard(key="predictive", name="Predictive Analytics / Anomaly Detection", category="analytics", status="implemented", practical_use="Lead scoring, market summary and outlier detection", source_module="layers.analytics"),
        CapabilityCard(key="geoint", name="Geospatial Intelligence", category="analytics", status="implemented", practical_use="Distance, area clustering and proximity duplicate detection", source_module="layers.geoint"),
        CapabilityCard(key="universal_agent", name="Universal Web Agent", category="research", status="guarded", safety_boundary="Compliance checks, confidence thresholds and manual review are mandatory", practical_use="Zero-shot extraction through safe policy/browser/LLM adapters", source_module="layers.ai_app"),
    ]
    return [card.model_dump(mode="json") for card in cards]
