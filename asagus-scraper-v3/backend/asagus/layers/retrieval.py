from __future__ import annotations

import math
import re
from hashlib import blake2b
from collections import Counter

from asagus.layers.policy import PolicyEngine
from asagus.layers.search_index import InvertedSearchIndex
from asagus.models import EnrichedRecord, ResearchSearchAlgorithm, SearchAlgorithm, SearchRequest, SearchResult


TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


class RetrievalLayer:
    """Layer 8 hybrid retrieval: BM25 + dense-like similarity + RRF + rerank hook."""

    def __init__(self, policy: PolicyEngine) -> None:
        self.policy = policy

    async def search(self, request: SearchRequest, records: list[EnrichedRecord]) -> list[SearchResult]:
        filtered = [record for record in records if self._passes_filters(request, record)]
        if not filtered:
            return []

        index = InvertedSearchIndex().build(filtered)
        candidate_ids = index.candidates(request.query)
        inverted_tfidf_rank = index.tfidf_rank(request.query, candidate_ids)
        bm25_rank = index.bm25_rank(request.query, candidate_ids)
        dense_rank = index.dense_rank(request.query, candidate_ids)
        ann_rank = index.ann_rank(request.query)
        learned_sparse_rank = self._learned_sparse_rank(request.query, filtered)
        late_interaction_rank = self._late_interaction_rank(request.query, filtered)
        muvera_rank = self._muvera_fde_rank(request.query, filtered)
        graph_rank = self._graph_guided_rank(request.query, filtered)
        fused = self._rrf_fuse(
            [inverted_tfidf_rank, bm25_rank, dense_rank, ann_rank, learned_sparse_rank, late_interaction_rank, muvera_rank, graph_rank],
            k=60,
        )

        results: list[SearchResult] = []
        for record_id, score in fused:
            record = next(record for record in filtered if record.id == record_id)
            results.append(
                SearchResult(
                    record=record,
                    score=index.ltr_score(request.query, record, score + index.cross_encoder_score(request.query, record) * 0.08),
                    source="rrf",
                    highlights=self._highlights(request.query, record),
                )
            )

        if self.policy.should_rerank(request, len(results)):
            results = self._policy_rerank(request, results)
        results = self._corrective_filter(request, results)
        return results[: request.top_k]

    def _bm25_rank(self, query: str, records: list[EnrichedRecord]) -> list[tuple[str, float]]:
        query_terms = self._tokens(query)
        documents = {record.id: self._tokens(self._record_text(record)) for record in records}
        avg_len = sum(len(tokens) for tokens in documents.values()) / max(len(documents), 1)
        doc_freq: Counter[str] = Counter()
        for tokens in documents.values():
            doc_freq.update(set(tokens))

        k1 = 1.5
        b = 0.75
        scores: list[tuple[str, float]] = []
        for record_id, tokens in documents.items():
            counts = Counter(tokens)
            score = 0.0
            for term in query_terms:
                if term not in counts:
                    continue
                idf = math.log(1 + (len(documents) - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
                tf = counts[term]
                denom = tf + k1 * (1 - b + b * (len(tokens) / max(avg_len, 1)))
                score += idf * ((tf * (k1 + 1)) / denom)
            if score > 0:
                scores.append((record_id, score))
        return sorted(scores, key=lambda item: item[1], reverse=True)

    def _dense_rank(self, query: str, records: list[EnrichedRecord]) -> list[tuple[str, float]]:
        query_vector = self._term_vector(self._tokens(query))
        scores: list[tuple[str, float]] = []
        for record in records:
            vector = self._term_vector(self._tokens(self._record_text(record)))
            score = self._cosine(query_vector, vector)
            if score > 0:
                scores.append((record.id, score))
        return sorted(scores, key=lambda item: item[1], reverse=True)

    def _learned_sparse_rank(self, query: str, records: list[EnrichedRecord]) -> list[tuple[str, float]]:
        expanded_query = self._expand_terms(self._tokens(query))
        scores: list[tuple[str, float]] = []
        for record in records:
            expanded_doc = self._expand_terms(self._tokens(self._record_text(record)))
            overlap = expanded_query.keys() & expanded_doc.keys()
            score = sum(min(expanded_query[token], expanded_doc[token]) for token in overlap)
            if score > 0:
                scores.append((record.id, score))
        return sorted(scores, key=lambda item: item[1], reverse=True)

    def _late_interaction_rank(self, query: str, records: list[EnrichedRecord]) -> list[tuple[str, float]]:
        query_terms = self._tokens(query)
        scores: list[tuple[str, float]] = []
        for record in records:
            doc_terms = self._tokens(self._record_text(record))
            if not doc_terms:
                continue
            max_sim_sum = 0.0
            for query_term in query_terms:
                max_sim_sum += max(self._token_similarity(query_term, doc_term) for doc_term in doc_terms)
            score = max_sim_sum / max(len(query_terms), 1)
            if score > 0.18:
                scores.append((record.id, score))
        return sorted(scores, key=lambda item: item[1], reverse=True)

    def _muvera_fde_rank(self, query: str, records: list[EnrichedRecord], dimensions: int = 64) -> list[tuple[str, float]]:
        query_tokens = self._tokens(query)
        query_fde = self._fixed_dimensional_encoding(query_tokens, dimensions, query_side=True)
        scores: list[tuple[str, float]] = []
        for record in records:
            doc_tokens = self._tokens(self._record_text(record))
            doc_fde = self._fixed_dimensional_encoding(doc_tokens, dimensions, query_side=False)
            score = self._dot(query_fde, doc_fde)
            if score > 0:
                scores.append((record.id, score))
        return sorted(scores, key=lambda item: item[1], reverse=True)

    def _graph_guided_rank(self, query: str, records: list[EnrichedRecord]) -> list[tuple[str, float]]:
        query_terms = set(self._tokens(query))
        scores: list[tuple[str, float]] = []
        for record in records:
            tags = set(self._tokens(" ".join(record.entity_tags)))
            graph_terms = tags | set(self._tokens(record.category)) | set(self._tokens(record.city))
            score = len(query_terms & graph_terms) * 0.35
            if "competitor" in query_terms and record.category:
                score += 0.20
            if "near" in query_terms or "area" in query_terms:
                score += 0.12 if record.city else 0.0
            if score > 0:
                scores.append((record.id, score))
        return sorted(scores, key=lambda item: item[1], reverse=True)

    def _rrf_fuse(self, rankings: list[list[tuple[str, float]]], k: int = 60) -> list[tuple[str, float]]:
        fused: Counter[str] = Counter()
        for ranking in rankings:
            for rank, (record_id, _score) in enumerate(ranking, start=1):
                fused[record_id] += 1 / (k + rank)
        return fused.most_common()

    def _policy_rerank(self, request: SearchRequest, results: list[SearchResult]) -> list[SearchResult]:
        query = request.query.lower()
        reranked: list[SearchResult] = []
        for result in results:
            bonus = 0.0
            if "whatsapp" in query and result.record.whatsapp:
                bonus += 0.08
            if "no website" in query and not result.record.website_url:
                bonus += 0.08
            if request.city and request.city.lower() == result.record.city.lower():
                bonus += 0.05
            reranked.append(result.model_copy(update={"score": round(result.score + bonus, 4)}))
        return sorted(reranked, key=lambda item: item.score, reverse=True)

    def _corrective_filter(self, request: SearchRequest, results: list[SearchResult]) -> list[SearchResult]:
        if not results:
            return results
        query_terms = set(self._tokens(request.query))
        corrected: list[SearchResult] = []
        for result in results:
            evidence_terms = set(self._tokens(" ".join(result.highlights) or self._record_text(result.record)))
            overlap = len(query_terms & evidence_terms) / max(len(query_terms), 1)
            if overlap == 0 and result.score < 0.05:
                continue
            penalty = 0.015 if overlap == 0 else 0.0
            corrected.append(result.model_copy(update={"score": round(max(0.0, result.score - penalty), 4)}))
        return sorted(corrected, key=lambda item: item.score, reverse=True)

    def chain_of_retrieval_queries(self, query: str, max_steps: int = 3) -> list[str]:
        tokens = self._tokens(query)
        queries = [query]
        if "without" in tokens or "no" in tokens:
            queries.append(f"{query} missing website missing email")
        if "competitor" in tokens or "near" in tokens:
            queries.append(f"{query} same category same city")
        if len(queries) < max_steps:
            queries.append(" ".join(tokens[:6] + ["contact", "business", "lead"]))
        return queries[:max_steps]

    def _passes_filters(self, request: SearchRequest, record: EnrichedRecord) -> bool:
        if request.city and request.city.lower() not in record.city.lower():
            return False
        if request.category and request.category.lower() not in record.category.lower():
            return False
        if request.has_website is not None and bool(record.website_url) != request.has_website:
            return False
        if request.has_whatsapp is not None and bool(record.whatsapp) != request.has_whatsapp:
            return False
        return True

    def _record_text(self, record: EnrichedRecord) -> str:
        return " ".join(
            [
                record.name,
                record.category,
                record.city,
                record.address,
                record.email,
                record.phone,
                record.whatsapp,
                record.website_url,
                " ".join(record.entity_tags),
            ]
        )

    def _highlights(self, query: str, record: EnrichedRecord) -> list[str]:
        terms = set(self._tokens(query))
        snippets = []
        for value in [record.name, record.category, record.city, record.address, record.email, record.phone]:
            if value and terms.intersection(self._tokens(value)):
                snippets.append(value)
        return snippets[:3]

    def _tokens(self, text: str) -> list[str]:
        return [token.lower() for token in TOKEN_RE.findall(text or "") if len(token) > 1]

    def _expand_terms(self, tokens: list[str]) -> Counter[str]:
        expansions = {
            "whatsapp": ["phone", "contact", "wa"],
            "restaurant": ["food", "dining", "menu", "cafe"],
            "clinic": ["doctor", "medical", "health"],
            "website": ["domain", "url", "site"],
            "lead": ["business", "company", "contact"],
        }
        vector: Counter[str] = Counter(tokens)
        for token in tokens:
            for expanded in expansions.get(token, []):
                vector[expanded] += 0.45
        return vector

    def _fixed_dimensional_encoding(self, tokens: list[str], dimensions: int, query_side: bool) -> list[float]:
        vector = [0.0] * dimensions
        if not tokens:
            return vector
        for position, token in enumerate(tokens):
            digest = blake2b(f"{token}:{position if query_side else 0}".encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 / math.sqrt(position + 1) if query_side else 1.0
            vector[bucket] += sign * weight
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def _dot(self, left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right))

    def _term_vector(self, tokens: list[str]) -> Counter[str]:
        return Counter(tokens)

    def _cosine(self, left: Counter[str], right: Counter[str]) -> float:
        if not left or not right:
            return 0.0
        dot = sum(left[token] * right[token] for token in left.keys() & right.keys())
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        return dot / max(left_norm * right_norm, 1e-9)

    def _token_similarity(self, left: str, right: str) -> float:
        if left == right:
            return 1.0
        if left in right or right in left:
            return 0.68
        left_set = set(left)
        right_set = set(right)
        return len(left_set & right_set) / max(len(left_set | right_set), 1)

    def algorithm_catalog(self) -> list[ResearchSearchAlgorithm]:
        return [
            ResearchSearchAlgorithm(
                name="Inverted Index",
                category=SearchAlgorithm.inverted_index,
                year=1950,
                role="Fast candidate generation by term-to-document postings",
                implementation_status="implemented",
                notes="Implemented in InvertedSearchIndex; maps to OpenSearch/Lucene in production.",
            ),
            ResearchSearchAlgorithm(
                name="TF-IDF",
                category=SearchAlgorithm.tfidf,
                year=1972,
                role="Classic lexical weighting for interpretable term relevance",
                implementation_status="implemented",
                notes="Implemented alongside BM25 for transparent fallback ranking.",
            ),
            ResearchSearchAlgorithm(
                name="Vector Embeddings",
                category=SearchAlgorithm.vector_embeddings,
                year=2013,
                role="Dense semantic representation for fuzzy matching",
                implementation_status="implemented",
                notes="Hash embeddings locally; sentence-transformer/Qdrant adapter for production vectors.",
            ),
            ResearchSearchAlgorithm(
                name="Approximate Nearest Neighbor Search",
                category=SearchAlgorithm.ann_search,
                year=2016,
                role="Fast vector candidate retrieval using approximate buckets",
                implementation_status="implemented",
                notes="Local LSH buckets now; Qdrant HNSW owns production ANN.",
            ),
            ResearchSearchAlgorithm(
                name="BM25",
                category=SearchAlgorithm.bm25,
                year=1994,
                role="High-precision lexical baseline and exact business term matching",
                implementation_status="implemented",
                notes="Implemented locally; maps to OpenSearch BM25 in production.",
            ),
            ResearchSearchAlgorithm(
                name="Learning to Rank",
                category=SearchAlgorithm.learning_to_rank,
                year=2005,
                role="Blend lexical, neural, business-quality and compliance features",
                implementation_status="implemented",
                notes="Feature-weighted LTR scorer implemented; LambdaMART/LightGBM adapter can replace weights.",
            ),
            ResearchSearchAlgorithm(
                name="Hybrid Retrieval",
                category=SearchAlgorithm.hybrid_retrieval,
                year=2020,
                role="Fuse BM25, TF-IDF, dense, ANN, sparse, late-interaction and graph signals",
                implementation_status="implemented",
                notes="Implemented through RRF fusion.",
            ),
            ResearchSearchAlgorithm(
                name="Dense Retrieval / Bi-Encoder",
                category=SearchAlgorithm.dense_bi_encoder,
                year=2020,
                role="Encode query and records independently for fast semantic retrieval",
                implementation_status="implemented",
                source_url="https://arxiv.org/abs/2004.04906",
                notes="Local vector fallback; DPR/SentenceTransformer adapter ready.",
            ),
            ResearchSearchAlgorithm(
                name="Dense HNSW",
                category=SearchAlgorithm.dense_hnsw,
                year=2016,
                role="Semantic nearest-neighbor retrieval for fuzzy business intent",
                implementation_status="adapter_ready",
                notes="Local cosine fallback now; Qdrant HNSW adapter owns production vectors.",
            ),
            ResearchSearchAlgorithm(
                name="Cross-Encoder Reranking",
                category=SearchAlgorithm.cross_encoder,
                year=2019,
                role="Jointly score query-record pairs after candidate retrieval",
                implementation_status="implemented",
                notes="Token-pair cross score implemented; BERT cross-encoder adapter ready.",
            ),
            ResearchSearchAlgorithm(
                name="BERT",
                category=SearchAlgorithm.bert,
                year=2018,
                role="Transformer encoder adapter for NER, reranking and embeddings",
                implementation_status="adapter_ready",
                source_url="https://arxiv.org/abs/1810.04805",
                notes="Fallbacks are deterministic; model slot is ready via sentence-transformers/GLiNER.",
            ),
            ResearchSearchAlgorithm(
                name="Transformer Attention",
                category=SearchAlgorithm.transformer_attention,
                year=2017,
                role="Attention-based term/entity weighting and neural adapters",
                implementation_status="adapter_ready",
                source_url="https://arxiv.org/abs/1706.03762",
                notes="Attention-style term weights are exposed in NLP intelligence.",
            ),
            ResearchSearchAlgorithm(
                name="RAG",
                category=SearchAlgorithm.rag,
                year=2020,
                role="Ground LLM summaries and actions in retrieved business records",
                implementation_status="implemented",
                notes="Search results feed the AI application layer summarizer.",
            ),
            ResearchSearchAlgorithm(
                name="RLHF / Human Feedback",
                category=SearchAlgorithm.rlhf,
                year=2017,
                role="Capture operator feedback as ranking and crawl reward data",
                implementation_status="adapter_ready",
                notes="Policy feedback exists; explicit thumbs-up/down endpoint is next.",
            ),
            ResearchSearchAlgorithm(
                name="Contrastive Learning",
                category=SearchAlgorithm.contrastive_learning,
                year=2020,
                role="DPR/SigLIP-style embedding training and similarity scoring",
                implementation_status="adapter_ready",
                notes="Hash contrastive embedding fallback; model-backed embedding adapter ready.",
            ),
            ResearchSearchAlgorithm(
                name="SPLADE / CSPLADE learned sparse retrieval",
                category=SearchAlgorithm.learned_sparse_splade,
                year=2025,
                role="Semantic expansion with inverted-index efficiency",
                implementation_status="adapter_ready",
                source_url="https://arxiv.org/abs/2504.10816",
                notes="Lightweight sparse expansion fallback now; full CSPLADE model can be dropped behind this interface.",
            ),
            ResearchSearchAlgorithm(
                name="ColBERT late interaction",
                category=SearchAlgorithm.late_interaction_colbert,
                year=2021,
                role="Token-level semantic matching for higher recall and ranking precision",
                implementation_status="adapter_ready",
                source_url="https://arxiv.org/abs/2112.01488",
                notes="Token max-sim fallback now; ColBERT/MUVERA backend can replace the scorer.",
            ),
            ResearchSearchAlgorithm(
                name="MUVERA multi-vector retrieval",
                category=SearchAlgorithm.muvera_multi_vector,
                year=2025,
                role="Fast multi-vector search before full late-interaction rerank",
                implementation_status="implemented",
                source_url="https://research.google/blog/muvera-making-multi-vector-retrieval-as-fast-as-single-vector-search/",
                notes="Practical fixed-dimensional sketch implemented; can be swapped for exact FDE/MIPS backend.",
            ),
            ResearchSearchAlgorithm(
                name="Reciprocal Rank Fusion",
                category=SearchAlgorithm.rrf_fusion,
                year=2009,
                role="Robustly fuse BM25, dense, sparse and late-interaction rankings",
                implementation_status="implemented",
                notes="Implemented with k=60.",
            ),
            ResearchSearchAlgorithm(
                name="Graph-guided retrieval / GraphRAG",
                category=SearchAlgorithm.graph_guided,
                year=2024,
                role="Use Neo4j relationships for area, competitor, network and duplicate-aware retrieval",
                implementation_status="adapter_ready",
                source_url="https://arxiv.org/abs/2408.08921",
                notes="Graph candidates are generated; Cypher retrieval adapter is next production step.",
            ),
            ResearchSearchAlgorithm(
                name="Clue-RAG Q-Iter",
                category=SearchAlgorithm.clue_rag_q_iter,
                year=2025,
                role="Iteratively expand graph-constrained retrieval around matched entities",
                implementation_status="adapter_ready",
                source_url="https://arxiv.org/abs/2507.08445",
                notes="Implemented as graph-guided score and chain query hooks; full multipartite graph index maps to Neo4j.",
            ),
            ResearchSearchAlgorithm(
                name="Chain-of-Retrieval",
                category=SearchAlgorithm.chain_of_retrieval,
                year=2025,
                role="Reformulate queries step-by-step when one-shot retrieval is weak",
                implementation_status="implemented",
                source_url="https://arxiv.org/abs/2501.14342",
                notes="Deterministic multi-step query generator is implemented for production-safe fallback.",
            ),
            ResearchSearchAlgorithm(
                name="Corrective RAG",
                category=SearchAlgorithm.corrective_rag,
                year=2024,
                role="Filter weak evidence and trigger additional retrieval/discovery when results are poor",
                implementation_status="implemented",
                source_url="https://arxiv.org/abs/2401.15884",
                notes="Implemented as evidence-overlap correction and ready to trigger DDGS discovery when enabled.",
            ),
            ResearchSearchAlgorithm(
                name="Causal Dynamic Feedback RAG",
                category=SearchAlgorithm.causal_feedback,
                year=2025,
                role="Prefer records connected by explainable graph paths, not only correlation",
                implementation_status="adapter_ready",
                source_url="https://arxiv.org/abs/2504.12560",
                notes="Relationship confidence and causal path hooks are represented in graph candidates.",
            ),
            ResearchSearchAlgorithm(
                name="Contextual bandit crawl exploration",
                category=SearchAlgorithm.contextual_bandit,
                year=2025,
                role="Balance crawl exploitation with exploration while learning page rewards",
                implementation_status="implemented",
                notes="UCB action bonus is implemented in the MDP scheduler.",
            ),
            ResearchSearchAlgorithm(
                name="Self-Healing Neural Scrapers",
                category=SearchAlgorithm.self_healing_scraper,
                year=2024,
                role="Recover selectors from DOM fingerprints, structure and LLM fallbacks",
                implementation_status="implemented",
                notes="Extraction cascade stores DOM fingerprints and routes to LLM/manual review by confidence.",
            ),
            ResearchSearchAlgorithm(
                name="ReAct Agent Pattern",
                category=SearchAlgorithm.react_agent,
                year=2022,
                role="Reason over policy/search state, then act through safe tools",
                implementation_status="adapter_ready",
                notes="AI application layer has the retrieval/action boundary; full agent loop remains guarded.",
            ),
            ResearchSearchAlgorithm(
                name="Sentiment Analysis",
                category=SearchAlgorithm.sentiment_analysis,
                year=2002,
                role="Detect quality/risk language in snippets, reviews and page text",
                implementation_status="implemented",
                notes="Local lexicon fallback added in NLP intelligence.",
            ),
            ResearchSearchAlgorithm(
                name="Named Entity Recognition",
                category=SearchAlgorithm.named_entity_recognition,
                year=1990,
                role="Extract organizations, services, locations and contacts",
                implementation_status="implemented",
                notes="Rule/record fallback plus GLiNER-ready adapter.",
            ),
            ResearchSearchAlgorithm(
                name="Text Summarization",
                category=SearchAlgorithm.text_summarization,
                year=1958,
                role="Summarize result sets and page evidence for users",
                implementation_status="implemented",
                notes="Extractive fallback plus LLM summarization when a provider is configured.",
            ),
            ResearchSearchAlgorithm(
                name="Google Dorking",
                category=SearchAlgorithm.google_dorking,
                year=2002,
                role="Public business discovery queries",
                implementation_status="guarded",
                notes="SafeOSINT blocks credential/session/admin dorks and keeps human review.",
            ),
            ResearchSearchAlgorithm(
                name="DOM Parsing",
                category=SearchAlgorithm.dom_parsing,
                year=1998,
                role="Extract structural page features and text",
                implementation_status="implemented",
                notes="DOMTools uses selectolax with regex fallback.",
            ),
            ResearchSearchAlgorithm(
                name="CSS Selector Matching",
                category=SearchAlgorithm.css_selector_matching,
                year=1996,
                role="Fast field extraction and selector recovery",
                implementation_status="implemented",
                notes="CSS matching is adapter-backed by selectolax.",
            ),
            ResearchSearchAlgorithm(
                name="XPath Querying",
                category=SearchAlgorithm.xpath_querying,
                year=1999,
                role="Structured extraction from XML/HTML trees",
                implementation_status="adapter_ready",
                notes="XPath adapter uses lxml when installed.",
            ),
            ResearchSearchAlgorithm(
                name="Safe API Sessions",
                category=SearchAlgorithm.safe_api_sessions,
                year=2000,
                role="Use documented public APIs and owned OAuth sessions only",
                implementation_status="guarded",
                notes="No API session exploitation, stolen cookies, replay or auth bypass.",
            ),
            ResearchSearchAlgorithm(
                name="Headless Browser Automation",
                category=SearchAlgorithm.headless_browser_automation,
                year=2017,
                role="Render JavaScript pages through Playwright Chromium",
                implementation_status="implemented",
                notes="Chromium pool is wired behind compliance/policy checks.",
            ),
            ResearchSearchAlgorithm(
                name="Graph / Network Analysis",
                category=SearchAlgorithm.graph_network_analysis,
                year=1970,
                role="Find duplicates, competitors, same-area and same-network relationships",
                implementation_status="implemented",
                notes="Relationship candidates are generated for Neo4j materialization.",
            ),
            ResearchSearchAlgorithm(
                name="Computer Vision",
                category=SearchAlgorithm.computer_vision,
                year=2012,
                role="Business media, logo, object and storefront classification",
                implementation_status="guarded",
                notes="Face identification/biometric recognition is disabled.",
            ),
            ResearchSearchAlgorithm(
                name="Predictive Analytics / Anomaly Detection",
                category=SearchAlgorithm.predictive_analytics,
                year=2000,
                role="Lead score prediction and outlier detection",
                implementation_status="implemented",
                notes="Lead scoring and z-score anomaly detection are implemented.",
            ),
            ResearchSearchAlgorithm(
                name="Geospatial Intelligence",
                category=SearchAlgorithm.geospatial_intelligence,
                year=1960,
                role="Area clustering, proximity duplicates and distance scoring",
                implementation_status="implemented",
                notes="Haversine, area clusters and proximity duplicate checks are implemented.",
            ),
            ResearchSearchAlgorithm(
                name="Universal Web Agent",
                category=SearchAlgorithm.universal_web_agent,
                year=2024,
                role="Zero-shot scraping with policy, browser, extraction and LLM adapters",
                implementation_status="guarded",
                notes="Production-safe version requires compliance checks and manual review below confidence thresholds.",
            ),
            ResearchSearchAlgorithm(
                name="Cross-Platform OSINT Fusion",
                category=SearchAlgorithm.osint_fusion,
                year=2024,
                role="Fuse public business pages across maps, websites and social business profiles",
                implementation_status="guarded",
                notes="Business-only, PII-minimized, human-review workflow.",
            ),
        ]
