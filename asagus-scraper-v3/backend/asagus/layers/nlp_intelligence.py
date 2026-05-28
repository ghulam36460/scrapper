from __future__ import annotations

import re
from collections import Counter

from asagus.models import EnrichedRecord


class NLPIntelligenceLayer:
    """BERT/Transformer-ready NLP facade with local deterministic fallbacks."""

    positive_words = {"good", "great", "best", "trusted", "top", "excellent", "professional", "recommended"}
    negative_words = {"bad", "poor", "fake", "closed", "complaint", "scam", "untrusted"}

    def analyze_record(self, record: EnrichedRecord) -> dict[str, object]:
        text = self._record_text(record)
        return {
            "sentiment": self.sentiment(text),
            "entities": self.ner(record),
            "summary": self.summarize(text),
            "attention_terms": self.transformer_attention_terms(text),
            "contrastive_embedding_preview": self.contrastive_embedding(text)[:8],
        }

    def sentiment(self, text: str) -> dict[str, object]:
        tokens = self.tokens(text)
        pos = sum(1 for token in tokens if token in self.positive_words)
        neg = sum(1 for token in tokens if token in self.negative_words)
        score = (pos - neg) / max(pos + neg, 1)
        label = "positive" if score > 0.15 else "negative" if score < -0.15 else "neutral"
        return {"label": label, "score": round(score, 3), "positive_hits": pos, "negative_hits": neg}

    def ner(self, record: EnrichedRecord) -> dict[str, list[str]]:
        entities = {
            "organization": [record.name] if record.name else [],
            "location": [item for item in [record.city, record.address] if item],
            "contact": [item for item in [record.email, record.phone, record.whatsapp] if item],
            "service": [record.category] if record.category else [],
        }
        for key, values in record.ner_entities.items():
            entities.setdefault(key, []).extend(values)
        return {key: sorted(set(values)) for key, values in entities.items() if values}

    def summarize(self, text: str, max_sentences: int = 2) -> str:
        sentences = [part.strip() for part in re.split(r"[.!?\n]+", text) if part.strip()]
        if not sentences:
            return ""
        term_counts = Counter(self.tokens(text))
        scored = []
        for sentence in sentences:
            score = sum(term_counts[token] for token in self.tokens(sentence))
            scored.append((score, sentence))
        return ". ".join(sentence for _score, sentence in sorted(scored, reverse=True)[:max_sentences])

    def transformer_attention_terms(self, text: str, top_k: int = 8) -> list[dict[str, object]]:
        tokens = self.tokens(text)
        counts = Counter(tokens)
        total = max(sum(counts.values()), 1)
        return [
            {"term": term, "attention": round(count / total, 4)}
            for term, count in counts.most_common(top_k)
        ]

    def contrastive_embedding(self, text: str, dimensions: int = 32) -> list[float]:
        vector = [0.0] * dimensions
        for token in self.tokens(text):
            bucket = hash(token) % dimensions
            vector[bucket] += 1.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [round(value / norm, 4) for value in vector]

    def _record_text(self, record: EnrichedRecord) -> str:
        return " ".join(
            [
                record.name,
                record.category,
                record.city,
                record.address,
                record.website_url,
                " ".join(record.entity_tags),
            ]
        )

    def tokens(self, text: str) -> list[str]:
        return [token.lower() for token in re.findall(r"[a-zA-Z0-9]+", text or "") if len(token) > 1]

    def state(self) -> dict[str, object]:
        return {
            "implemented": ["sentiment_analysis", "ner_fallback", "extractive_summarization", "attention_term_weights", "contrastive_hash_embedding"],
            "adapter_ready": ["bert", "transformer_encoder", "siglip_or_dpr_contrastive_models", "abstractive_summarization"],
        }
