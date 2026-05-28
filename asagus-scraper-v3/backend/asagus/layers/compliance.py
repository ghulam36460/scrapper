from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlparse

from asagus.models import ComplianceDecision, URLCandidate


EU_TLDS = {".at", ".be", ".de", ".dk", ".es", ".fi", ".fr", ".ie", ".it", ".nl", ".pl", ".pt", ".se"}
HONEYPOT_MARKERS = ("trap", "honeypot", "bot-check", "do-not-crawl", "hidden-link", "crawler-test")
BLOCK_MARKERS = ("blocked", "forbidden", "access-denied", "captcha", "verify-you-are-human", "challenge")


class BlocklistHoneypotDetector:
    """Detects blocked/trap URLs and routes them to audit instead of bypass."""

    def classify(self, candidate: URLCandidate, host: str, path: str, blocked_domains: list[str]) -> tuple[bool, str, dict[str, object]]:
        lower_blocked = [domain.lower() for domain in blocked_domains]
        if any(host.endswith(domain) for domain in lower_blocked):
            return True, "blocked_by_job_policy", {"matched_domains": lower_blocked}
        marker_text = " ".join(
            [
                path,
                str(candidate.metadata.get("rel", "")),
                str(candidate.metadata.get("css", "")),
                str(candidate.metadata.get("text", "")),
                str(candidate.metadata.get("html_markers", "")),
            ]
        ).lower()
        if candidate.metadata.get("hidden") is True or any(marker in marker_text for marker in HONEYPOT_MARKERS):
            return True, "honeypot_or_hidden_link_detected", {"markers": [marker for marker in HONEYPOT_MARKERS if marker in marker_text]}
        if any(marker in marker_text for marker in BLOCK_MARKERS):
            return True, "access_challenge_or_block_detected", {"markers": [marker for marker in BLOCK_MARKERS if marker in marker_text]}
        return False, "clear", {}


@dataclass
class TokenBucket:
    capacity: float
    refill_per_second: float
    tokens: float
    updated_at: float

    def consume(self, amount: float = 1.0) -> tuple[bool, float, float]:
        now = time.monotonic()
        elapsed = now - self.updated_at
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
        self.updated_at = now
        if self.tokens >= amount:
            self.tokens -= amount
            return True, 0.0, self.tokens
        wait = (amount - self.tokens) / max(self.refill_per_second, 0.001)
        return False, wait, self.tokens


class ComplianceLayer:
    """Layer 2 compliance, robots cache facade, token bucket and audit hints."""

    _buckets: dict[str, TokenBucket] = {}
    _robots_cache: dict[str, tuple[float, bool, float | None]] = {}
    _quarantine: dict[str, dict[str, object]] = {}

    def __init__(
        self,
        unknown_domain_delay_seconds: float = 2.0,
        token_capacity: int = 8,
        token_refill_per_second: float = 0.25,
        robots_cache_ttl_seconds: int = 86_400,
    ) -> None:
        self.unknown_domain_delay_seconds = unknown_domain_delay_seconds
        self.token_capacity = token_capacity
        self.token_refill_per_second = token_refill_per_second
        self.robots_cache_ttl_seconds = robots_cache_ttl_seconds
        self.detector = BlocklistHoneypotDetector()

    def check(self, candidate: URLCandidate, allowed_domains: list[str], blocked_domains: list[str]) -> ComplianceDecision:
        parsed = urlparse(candidate.url)
        host = parsed.netloc.lower()
        path = parsed.path.lower()

        if not host:
            return ComplianceDecision(allowed=False, delay_seconds=0, reason="invalid_url", audit_required=True)

        detected, reason, evidence = self.detector.classify(candidate, host, path, blocked_domains)
        if detected:
            self._quarantine[candidate.url] = {
                "reason": reason,
                "evidence": evidence,
                "review_path": "manual_allowlist_review_required",
            }
            return ComplianceDecision(
                allowed=False,
                delay_seconds=0,
                reason=reason,
                audit_required=True,
                crawl_delay_source="job_policy",
                gdpr_region=self._is_gdpr_domain(host),
            )

        if allowed_domains and not any(host.endswith(domain.lower()) for domain in allowed_domains):
            return ComplianceDecision(
                allowed=False,
                delay_seconds=0,
                reason="outside_job_allowlist",
                audit_required=True,
                crawl_delay_source="job_policy",
                gdpr_region=self._is_gdpr_domain(host),
            )

        robots_allowed, robots_cache_hit, robots_delay = self._robots_decision(host, path)
        if not robots_allowed:
            return ComplianceDecision(
                allowed=False,
                delay_seconds=0,
                reason="blocked_by_robots_cache",
                audit_required=True,
                robots_cache_hit=robots_cache_hit,
                crawl_delay_source="robots",
                gdpr_region=self._is_gdpr_domain(host),
            )

        bucket = self._bucket_for(host)
        token_ok, token_wait, tokens_left = bucket.consume()
        delay = max(
            robots_delay if robots_delay is not None else 0.0,
            token_wait,
            0.5 if "google.com" in host else self.unknown_domain_delay_seconds,
        )
        return ComplianceDecision(
            allowed=token_ok,
            delay_seconds=round(delay, 2),
            reason="allowed_with_token_bucket" if token_ok else "domain_rate_limited",
            audit_required=True,
            robots_cache_hit=robots_cache_hit,
            crawl_delay_source="robots" if robots_delay is not None else "token_bucket",
            gdpr_region=self._is_gdpr_domain(host),
            tokens_remaining=round(tokens_left, 2),
        )

    def _bucket_for(self, host: str) -> TokenBucket:
        bucket = self._buckets.get(host)
        if bucket:
            return bucket
        bucket = TokenBucket(
            capacity=float(self.token_capacity),
            refill_per_second=self.token_refill_per_second,
            tokens=float(self.token_capacity),
            updated_at=time.monotonic(),
        )
        self._buckets[host] = bucket
        return bucket

    def _robots_decision(self, host: str, path: str) -> tuple[bool, bool, float | None]:
        cached = self._robots_cache.get(host)
        now = time.time()
        if cached and now - cached[0] <= self.robots_cache_ttl_seconds:
            return cached[1], True, cached[2]

        # The fetch of robots.txt belongs to the network-enabled worker. This
        # local facade still persists the decision shape and 24h TTL contract.
        allowed = not any(marker in path for marker in ["/private", "/admin", "/wp-admin"])
        crawl_delay = 0.5 if "google.com" in host else None
        self._robots_cache[host] = (now, allowed, crawl_delay)
        return allowed, False, crawl_delay

    def _is_gdpr_domain(self, host: str) -> bool:
        return any(host.endswith(tld) for tld in EU_TLDS)

    def stats(self) -> dict[str, object]:
        return {
            "robots_cache_entries": len(self._robots_cache),
            "token_buckets": len(self._buckets),
            "quarantined_urls": len(self._quarantine),
            "robots_cache_ttl_hours": round(self.robots_cache_ttl_seconds / 3600, 2),
            "token_bucket_capacity": self.token_capacity,
            "token_refill_per_second": self.token_refill_per_second,
            "blocklist_honeypot_policy": "detect, quarantine, audit, manual allowlist review; no bypass/unlock automation",
        }
