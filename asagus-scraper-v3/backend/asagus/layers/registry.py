from __future__ import annotations

from typing import Any


ORDERED_LAYER_BLUEPRINT: list[dict[str, Any]] = [
    {"id": 0, "key": "policy", "name": "Policy Engine", "status": "rules_bayesian_feedback"},
    {"id": 1, "key": "crawl_control", "name": "Crawl Control Plane", "status": "mdp_frontier_scheduler"},
    {"id": 2, "key": "compliance", "name": "Compliance Layer", "status": "robots_token_bucket_audit"},
    {"id": 3, "key": "social_auth", "name": "Social Auth Layer", "status": "facebook_instagram_session_isolation"},
    {"id": 4, "key": "fetch", "name": "Fetch Layer", "status": "static_dynamic_proxy_pool"},
    {"id": 5, "key": "extraction", "name": "Extraction Layer", "status": "self_healing_cascade"},
    {"id": 6, "key": "enrichment", "name": "Enrichment Layer", "status": "ner_validation_dedupe"},
    {"id": 7, "key": "storage", "name": "Storage Layer", "status": "local_and_postgres_contracts"},
    {"id": 8, "key": "indexing", "name": "Indexing Layer", "status": "opensearch_qdrant_contracts"},
    {"id": 9, "key": "retrieval", "name": "Retrieval Layer", "status": "bm25_dense_rrf"},
    {"id": 10, "key": "ai_app", "name": "AI Application Layer", "status": "any_llm_provider_registry"},
]


def ordered_blueprint_layers() -> list[dict[str, Any]]:
    return [dict(layer) for layer in ORDERED_LAYER_BLUEPRINT]
