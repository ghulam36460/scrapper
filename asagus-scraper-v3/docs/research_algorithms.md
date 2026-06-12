# ASAGUS 3.0 Research Algorithms

This project turns recent retrieval and scheduling research into production-safe approximations first, with adapter points for heavier models later.

## Implemented Now

- BM25 lexical ranking for exact business/category/location matching.
- Inverted index candidate generation.
- TF-IDF transparent lexical scoring.
- Dense cosine ranking as the local Qdrant/HNSW-compatible fallback.
- Hash-vector embeddings and local ANN/LSH buckets.
- Learning-to-rank feature blending for quality, contactability, compliance and duplicate risk.
- Cross-encoder-style pair scoring as a local reranking fallback.
- SPLADE/CSPLADE-style learned sparse expansion with an inverted-index-friendly sparse vector.
- ColBERT-style late interaction using token max-sim scoring.
- MUVERA-style fixed-dimensional encoding sketches for fast multi-vector approximation.
- Reciprocal Rank Fusion across BM25, dense, sparse, late-interaction, MUVERA and graph-guided ranks.
- Chain-of-Retrieval query reformulation when one-shot retrieval is weak.
- Corrective RAG evidence filtering before returning results.
- GraphRAG/Clue-RAG adapter using entity tags, categories, cities and relationship candidates.
- Strong MDP crawl control: abstract Markov state buckets, action-specific transition probabilities, value iteration, Q-value policy selection, online reward updates and UCB contextual bandit exploration.
- Sentiment analysis, NER, extractive summarization, attention-term weighting and contrastive hash embeddings.
- DOM parsing, CSS selector matching and XPath adapter support.
- Public-business Google dork templates with guardrails against credential/session/admin queries.
- Playwright Chromium dynamic rendering.
- Lead-score prediction, z-score anomaly detection, GEOINT clustering and proximity duplicate checks.
- Computer-vision adapter for business media with face identification disabled.

## Primary Sources Used

- MUVERA: https://arxiv.org/abs/2405.19504
- CSPLADE: https://arxiv.org/abs/2504.10816
- Chain-of-Retrieval Augmented Generation: https://arxiv.org/abs/2501.14342
- Corrective Retrieval Augmented Generation: https://arxiv.org/abs/2401.15884
- CDF-RAG: https://arxiv.org/abs/2504.12560
- Clue-RAG: https://arxiv.org/abs/2507.08445
- ColBERTv2: https://arxiv.org/abs/2112.01488
- GraphRAG survey: https://arxiv.org/abs/2408.08921
- DPR dense retrieval: https://arxiv.org/abs/2004.04906
- BERT: https://arxiv.org/abs/1810.04805
- Transformer attention: https://arxiv.org/abs/1706.03762

## Safety Boundaries

- API session exploitation is not implemented. Only documented public APIs and owned OAuth/API keys are supported.
- Google dorking is limited to public business discovery. Credential, token, session, admin and exposed-secret dorks are blocked.
- Face identification and biometric recognition are disabled.
- Universal web-agent and cross-platform OSINT fusion features remain guarded by compliance checks, confidence thresholds, PII minimization and human review.

## Production Adapter Plan

- Replace local dense cosine with Qdrant HNSW embeddings.
- Replace sparse expansion with a real SPLADE/CSPLADE model when GPU/CPU budget is available.
- Replace local late-interaction max-sim with ColBERT or a MUVERA-backed MIPS index.
- Materialize graph-guided retrieval as Neo4j Cypher traversals over relationship candidates.
- Feed crawl rewards back into the MDP scheduler from Redis Streams worker results.

## Crawl MDP Details

The scheduler models `P(outcome | abstract_state, action)` with outcomes:

- `full`
- `partial`
- `dead`
- `deferred`
- `skipped`
- `banned`

The abstract state key includes URL type, depth band, domain yield band, ban-rate band, extraction confidence band and render/static mode. Value iteration computes a policy over all state-action pairs, then runtime rewards update state-action histories. The UI exposes state-space size, discount, iterations, outcomes and the current best-action policy snapshot.
