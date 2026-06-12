from __future__ import annotations

import math
from collections import Counter, defaultdict
from hashlib import blake2b
from typing import Iterable

from asagus.models import EnrichedRecord


class InvertedSearchIndex:
    """Inverted index, TF-IDF, BM25, hash embeddings, ANN buckets and LTR features."""

    def __init__(self) -> None:
        self.documents: dict[str, list[str]] = {}
        self.records: dict[str, EnrichedRecord] = {}
        self.inverted: dict[str, set[str]] = defaultdict(set)
        self.doc_freq: Counter[str] = Counter()
        self.doc_len: dict[str, int] = {}
        self.avg_len = 1.0
        self.ann_buckets: dict[int, set[str]] = defaultdict(set)

    def build(self, records: Iterable[EnrichedRecord]) -> "InvertedSearchIndex":
        self.documents.clear()
        self.records.clear()
        self.inverted.clear()
        self.doc_freq.clear()
        self.doc_len.clear()
        self.ann_buckets.clear()
        for record in records:
            tokens = self.tokens(self.record_text(record))
            self.records[record.id] = record
            self.documents[record.id] = tokens
            self.doc_len[record.id] = len(tokens)
            for token in set(tokens):
                self.inverted[token].add(record.id)
                self.doc_freq[token] += 1
            for bucket in self.ann_signature(tokens):
                self.ann_buckets[bucket].add(record.id)
        self.avg_len = sum(self.doc_len.values()) / max(len(self.doc_len), 1)
        return self

    def candidates(self, query: str) -> set[str]:
        out: set[str] = set()
        for token in self.tokens(query):
            out.update(self.inverted.get(token, set()))
        if out:
            return out
        for bucket in self.ann_signature(self.tokens(query)):
            out.update(self.ann_buckets.get(bucket, set()))
        return out or set(self.documents)

    def tfidf_rank(self, query: str, candidate_ids: Iterable[str] | None = None) -> list[tuple[str, float]]:
        query_vector = self.tfidf_vector(self.tokens(query), is_query=True)
        ids = list(candidate_ids or self.documents.keys())
        scores = []
        for record_id in ids:
            score = self.cosine(query_vector, self.tfidf_vector(self.documents.get(record_id, [])))
            if score > 0:
                scores.append((record_id, score))
        return sorted(scores, key=lambda item: item[1], reverse=True)

    def bm25_rank(self, query: str, candidate_ids: Iterable[str] | None = None) -> list[tuple[str, float]]:
        query_terms = self.tokens(query)
        ids = list(candidate_ids or self.documents.keys())
        k1 = 1.5
        b = 0.75
        n_docs = max(len(self.documents), 1)
        scores: list[tuple[str, float]] = []
        for record_id in ids:
            tokens = self.documents.get(record_id, [])
            counts = Counter(tokens)
            score = 0.0
            for term in query_terms:
                if term not in counts:
                    continue
                idf = math.log(1 + (n_docs - self.doc_freq[term] + 0.5) / (self.doc_freq[term] + 0.5))
                tf = counts[term]
                denom = tf + k1 * (1 - b + b * (len(tokens) / max(self.avg_len, 1)))
                score += idf * ((tf * (k1 + 1)) / max(denom, 1e-9))
            if score > 0:
                scores.append((record_id, score))
        return sorted(scores, key=lambda item: item[1], reverse=True)

    def dense_rank(self, query: str, candidate_ids: Iterable[str] | None = None) -> list[tuple[str, float]]:
        query_vector = self.hash_embedding(self.tokens(query))
        ids = list(candidate_ids or self.documents.keys())
        scores = []
        for record_id in ids:
            score = self.cosine(query_vector, self.hash_embedding(self.documents.get(record_id, [])))
            if score > 0:
                scores.append((record_id, score))
        return sorted(scores, key=lambda item: item[1], reverse=True)

    def ann_rank(self, query: str) -> list[tuple[str, float]]:
        ids = self.candidates(query)
        return self.dense_rank(query, ids)

    def ltr_score(self, query: str, record: EnrichedRecord, base_score: float) -> float:
        query_terms = set(self.tokens(query))
        text_terms = set(self.tokens(self.record_text(record)))
        term_overlap = len(query_terms & text_terms) / max(len(query_terms), 1)
        quality = record.record_completeness * 0.18 + record.confidence * 0.12
        contact_bonus = 0.08 if record.phone or record.whatsapp or record.email else 0.0
        geo_bonus = 0.06 if record.city and record.city.lower() in query.lower() else 0.0
        duplicate_penalty = record.duplicate_score * 0.15
        return round(base_score + term_overlap * 0.22 + quality + contact_bonus + geo_bonus - duplicate_penalty, 4)

    def cross_encoder_score(self, query: str, record: EnrichedRecord) -> float:
        q_tokens = self.tokens(query)
        d_tokens = self.tokens(self.record_text(record))
        if not q_tokens or not d_tokens:
            return 0.0
        pair_scores = []
        for q_token in q_tokens:
            pair_scores.append(max(self.token_similarity(q_token, d_token) for d_token in d_tokens))
        return round(sum(pair_scores) / len(pair_scores), 4)

    def tfidf_vector(self, tokens: list[str], is_query: bool = False) -> Counter[str]:
        counts = Counter(tokens)
        vector: Counter[str] = Counter()
        n_docs = max(len(self.documents), 1)
        for token, tf in counts.items():
            df = self.doc_freq[token] if not is_query else max(self.doc_freq[token], 1)
            idf = math.log((n_docs + 1) / (df + 1)) + 1
            vector[token] = (1 + math.log(tf)) * idf
        return vector

    def hash_embedding(self, tokens: list[str], dimensions: int = 128) -> Counter[int]:
        vector: Counter[int] = Counter()
        for token in tokens:
            digest = blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % dimensions
            sign = 1 if digest[4] % 2 == 0 else -1
            vector[bucket] += sign
        return vector

    def ann_signature(self, tokens: list[str], bands: int = 8) -> list[int]:
        vector = self.hash_embedding(tokens, dimensions=64)
        signature = []
        for band in range(bands):
            value = 0
            for offset in range(8):
                dim = band * 8 + offset
                if vector.get(dim, 0) >= 0:
                    value |= 1 << offset
            signature.append((band << 8) + value)
        return signature

    def cosine(self, left: Counter, right: Counter) -> float:
        if not left or not right:
            return 0.0
        dot = sum(left[key] * right[key] for key in left.keys() & right.keys())
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        return dot / max(left_norm * right_norm, 1e-9)

    def token_similarity(self, left: str, right: str) -> float:
        if left == right:
            return 1.0
        if left in right or right in left:
            return 0.72
        left_set = set(left)
        right_set = set(right)
        return len(left_set & right_set) / max(len(left_set | right_set), 1)

    def record_text(self, record: EnrichedRecord) -> str:
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

    def tokens(self, text: str) -> list[str]:
        return [token.lower() for token in __import__("re").findall(r"[a-zA-Z0-9]+", text or "") if len(token) > 1]

    def state(self) -> dict[str, object]:
        return {
            "documents": len(self.documents),
            "terms": len(self.inverted),
            "ann_buckets": len(self.ann_buckets),
            "algorithms": ["inverted_index", "tfidf", "bm25", "hash_embeddings", "ann_lsh", "ltr_features", "cross_encoder_heuristic"],
        }
