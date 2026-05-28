from __future__ import annotations

import math
from collections import Counter
from datetime import datetime
from pathlib import PurePosixPath
from urllib.parse import urlparse

from asagus.models import (
    DomainPolicyState,
    ExtractionMethod,
    FetchMode,
    FrontierTier,
    MDPAction,
    PolicyDecision,
    PolicyFeedback,
    SearchRequest,
    URLCandidate,
    URLType,
    utc_now,
)


ASSET_EXTENSIONS = {
    ".pdf",
    ".zip",
    ".rar",
    ".7z",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".mp4",
    ".mov",
}


class PolicyEngine:
    """Layer 0: rule-first, Bayesian-second, feedback-aware policy engine."""

    _domain_state: dict[str, DomainPolicyState] = {}
    _counters: Counter[str] = Counter()

    js_heavy_hosts = ("maps.google.", "facebook.com", "instagram.com", "linkedin.com", "x.com", "twitter.com")
    js_framework_markers = ("__next", "nuxt", "react", "vue", "angular", "svelte", "hydration")
    contact_markers = ("contact", "about", "reach-us", "reach_us", "location", "branches", "team")

    def decide_for_url(self, candidate: URLCandidate, llm_enabled: bool = True) -> PolicyDecision:
        parsed = urlparse(candidate.url)
        host = parsed.netloc.lower()
        path = parsed.path.lower() or "/"
        domain_state = self._state_for(host, candidate)

        rule_decision = self._apply_rule_layer(candidate, domain_state, llm_enabled)
        if rule_decision:
            self._counters["rule_layer_hits"] += 1
            domain_state.rule_hits += 1
            domain_state.pages_seen += 1
            return rule_decision

        bayes = self._bayesian_probability(candidate, domain_state)
        self._counters["bayesian_hits"] += 1
        domain_state.bayesian_hits += 1
        domain_state.pages_seen += 1

        if bayes < 0.18:
            return PolicyDecision(
                decision="skip",
                fetch_mode=FetchMode.static,
                extraction_method=ExtractionMethod.manual_review,
                should_index=False,
                should_archive=False,
                confidence=round(1 - bayes, 3),
                reasons=["Bayesian classifier predicts low extraction yield"],
                rules_fired=[],
                fallback="bayesian_skip",
                policy_layer="bayesian",
                bayesian_score=round(bayes, 3),
                quality_score=self.quality_estimate(candidate),
                frontier_tier=FrontierTier.blocked,
                mdp_action=MDPAction.skip,
            )

        fetch_mode = FetchMode.dynamic if self._requires_render(candidate, domain_state) else FetchMode.static
        extraction_method = self._method_from_confidence(domain_state.extraction_confidence_avg, llm_enabled)
        tier = self._tier_for_score(bayes)
        return PolicyDecision(
            decision="crawl" if bayes >= 0.35 else "defer",
            fetch_mode=fetch_mode,
            extraction_method=extraction_method,
            should_index=bayes >= 0.35,
            should_archive=True,
            confidence=round(max(bayes, 0.51), 3),
            reasons=[
                "Bayesian classifier handled unclear URL",
                f"path_depth={self._path_depth(path)}",
                f"domain_yield={domain_state.domain_yield_rate:.2f}",
            ],
            fallback="bayesian_policy",
            policy_layer="bayesian",
            bayesian_score=round(bayes, 3),
            quality_score=self.quality_estimate(candidate),
            frontier_tier=tier,
            mdp_action=MDPAction.crawl_now if bayes >= 0.55 else MDPAction.defer_1h,
            next_review_seconds=0 if bayes >= 0.55 else 3600,
        )

    def _apply_rule_layer(
        self,
        candidate: URLCandidate,
        domain_state: DomainPolicyState,
        llm_enabled: bool,
    ) -> PolicyDecision | None:
        parsed = urlparse(candidate.url)
        host = parsed.netloc.lower()
        path = parsed.path.lower() or "/"
        suffix = PurePosixPath(path).suffix.lower()
        rules: list[str] = []
        reasons: list[str] = []

        allowlist = [item.lower() for item in candidate.metadata.get("allowed_domains", [])]
        blocklist = [item.lower() for item in candidate.metadata.get("blocked_domains", [])]

        if blocklist and any(host.endswith(domain) for domain in blocklist):
            return PolicyDecision(
                decision="skip",
                should_index=False,
                should_archive=False,
                confidence=0.99,
                reasons=["Domain is in the blocklist"],
                rules_fired=["blocklist_skip"],
                fallback="rule_blocklist",
                frontier_tier=FrontierTier.blocked,
                mdp_action=MDPAction.skip,
            )

        if allowlist and any(host.endswith(domain) for domain in allowlist):
            rules.append("allowlist_always_crawl")
            reasons.append("Domain is in the allowlist")

        if suffix in ASSET_EXTENSIONS:
            return PolicyDecision(
                decision="skip",
                fetch_mode=FetchMode.static,
                extraction_method=ExtractionMethod.manual_review,
                should_index=False,
                should_archive=False,
                confidence=0.98,
                reasons=[f"Static asset extension {suffix} is skipped"],
                rules_fired=["asset_extension_skip"],
                fallback="rule_asset_skip",
                frontier_tier=FrontierTier.blocked,
                mdp_action=MDPAction.skip,
            )

        fetch_mode = FetchMode.static
        extraction_method = ExtractionMethod.css
        confidence = 0.74
        tier = candidate.frontier_tier

        if any(marker in path for marker in self.contact_markers):
            rules.append("contact_about_high_priority")
            reasons.append("Contact/about/reach-us URL has high lead yield")
            confidence = max(confidence, 0.88)
            tier = FrontierTier.high

        if domain_state.extraction_confidence_avg > 0.92:
            rules.append("high_confidence_css_skip_llm")
            reasons.append("Domain has high extraction confidence; CSS path preferred")
            extraction_method = ExtractionMethod.css
            confidence = max(confidence, 0.93)

        if domain_state.extraction_confidence_avg < 0.40 and llm_enabled:
            rules.append("low_confidence_go_llm")
            reasons.append("Domain extraction confidence is low; LLM fallback is routed early")
            extraction_method = ExtractionMethod.llm
            confidence = max(confidence, 0.81)

        if self._requires_render(candidate, domain_state):
            rules.append("domain_render_required")
            reasons.append("Domain or URL pattern requires browser rendering")
            fetch_mode = FetchMode.dynamic
            confidence = max(confidence, 0.86)

        if "wa.me" in candidate.url.lower() or "whatsapp" in candidate.url.lower():
            rules.append("whatsapp_fast_path")
            reasons.append("WhatsApp URL can be extracted without LLM")
            extraction_method = ExtractionMethod.css
            confidence = max(confidence, 0.91)

        if candidate.domain_yield_rate < 0.16 and candidate.depth > 1:
            return PolicyDecision(
                decision="skip",
                fetch_mode=fetch_mode,
                extraction_method=ExtractionMethod.manual_review,
                should_index=False,
                should_archive=False,
                confidence=0.82,
                reasons=["Low historical yield and deeper path"],
                rules_fired=["low_yield_deep_skip"],
                fallback="rule_low_yield",
                frontier_tier=FrontierTier.blocked,
                mdp_action=MDPAction.skip,
            )

        if rules:
            return PolicyDecision(
                decision="crawl",
                fetch_mode=fetch_mode,
                extraction_method=extraction_method,
                should_index=True,
                should_archive=True,
                confidence=round(confidence, 3),
                reasons=reasons,
                rules_fired=rules,
                fallback="rule_layer",
                policy_layer="rules",
                bayesian_score=0.0,
                quality_score=self.quality_estimate(candidate),
                frontier_tier=tier,
                mdp_action=MDPAction.crawl_now,
            )

        return None

    def _bayesian_probability(self, candidate: URLCandidate, state: DomainPolicyState) -> float:
        parsed = urlparse(candidate.url)
        path = parsed.path.lower() or "/"
        host = parsed.netloc.lower()
        features = {
            "good_tld": host.endswith((".com", ".org", ".net", ".pk", ".ae", ".sa", ".co", ".io")),
            "shallow_path": self._path_depth(path) <= 2,
            "contactish": any(marker in path for marker in self.contact_markers),
            "large_page": int(candidate.metadata.get("page_size_estimate", 0) or 0) > 120_000,
            "js_framework": self._has_js_framework(candidate),
            "business_hours": 8 <= datetime.now().hour <= 20,
            "known_yield": state.domain_yield_rate >= 0.45,
            "ban_pressure": state.domain_ban_rate > 0.25 or candidate.domain_ban_rate > 0.25,
        }
        likelihoods = {
            "good_tld": (0.64, 0.42),
            "shallow_path": (0.70, 0.38),
            "contactish": (0.83, 0.18),
            "large_page": (0.46, 0.58),
            "js_framework": (0.54, 0.42),
            "business_hours": (0.56, 0.50),
            "known_yield": (0.78, 0.22),
            "ban_pressure": (0.22, 0.71),
        }
        prior = max(0.05, min(0.95, 0.25 + state.domain_yield_rate * 0.55 + candidate.priority * 0.20))
        log_good = math.log(prior)
        log_bad = math.log(1 - prior)
        for name, value in features.items():
            p_good, p_bad = likelihoods[name]
            if not value:
                p_good, p_bad = 1 - p_good, 1 - p_bad
            log_good += math.log(max(p_good, 0.001))
            log_bad += math.log(max(p_bad, 0.001))
        good = math.exp(log_good)
        bad = math.exp(log_bad)
        return good / (good + bad)

    def record_feedback(self, feedback: PolicyFeedback) -> DomainPolicyState:
        state = self._domain_state.get(feedback.domain) or DomainPolicyState(domain=feedback.domain)
        state.pages_seen += 1
        state.llm_calls += 1 if feedback.used_llm else 0
        state.browser_renders += 1 if feedback.used_browser else 0
        state.domain_ban_rate = self._moving_average(state.domain_ban_rate, 1.0 if feedback.was_blocked else 0.0, 0.20)
        state.extraction_confidence_avg = self._moving_average(
            state.extraction_confidence_avg,
            feedback.extraction_confidence,
            0.15,
        )
        state.domain_yield_rate = self._moving_average(
            state.domain_yield_rate,
            min(1.0, feedback.fields_extracted / 8),
            0.15,
        )
        state.domain_render_required = state.browser_renders > 2 and state.browser_renders / max(state.pages_seen, 1) > 0.45
        state.last_feedback_at = utc_now()
        self._domain_state[feedback.domain] = state
        return state

    def quality_estimate(self, candidate: URLCandidate) -> float:
        contact_bonus = 0.18 if any(marker in candidate.url.lower() for marker in self.contact_markers) else 0.0
        maps_bonus = 0.15 if "google.com/maps" in candidate.url.lower() else 0.0
        depth_penalty = min(candidate.depth * 0.06, 0.28)
        ban_penalty = max(candidate.domain_ban_rate, 0.0) * 0.30
        value = (
            candidate.priority * 0.25
            + candidate.domain_yield_rate * 0.35
            + candidate.parent_page_yield * 0.15
            + candidate.last_extraction_confidence * 0.20
            + contact_bonus
            + maps_bonus
            - depth_penalty
            - ban_penalty
        )
        return round(max(0.0, min(1.0, value)), 3)

    def should_rerank(self, request: SearchRequest, candidate_count: int) -> bool:
        complex_query = len(request.query.split()) >= 5 or any(
            value is not None and value != ""
            for value in [request.city, request.category, request.has_website, request.has_whatsapp]
        )
        return request.rerank and complex_query and candidate_count > 5

    def stats(self) -> dict[str, float | int | str | dict[str, int] | list[str]]:
        pages_seen = sum(state.pages_seen for state in self._domain_state.values())
        llm_calls = sum(state.llm_calls for state in self._domain_state.values())
        browser_renders = sum(state.browser_renders for state in self._domain_state.values())
        return {
            "mode": "rule_bayesian_feedback",
            "rule_layer_target_hit_rate": 0.80,
            "rule_layer_hits": int(self._counters["rule_layer_hits"]),
            "bayesian_hits": int(self._counters["bayesian_hits"]),
            "llm_call_percent": round((llm_calls / max(pages_seen, 1)) * 100, 2),
            "browser_render_percent": round((browser_renders / max(pages_seen, 1)) * 100, 2),
            "tracked_domains": len(self._domain_state),
            "mdp_phase": "auto_by_crawl_count",
            "rules": [
                "allowlist_always_crawl",
                "blocklist_skip",
                "contact_about_high_priority",
                "asset_extension_skip",
                "high_confidence_css_skip_llm",
                "low_confidence_go_llm",
                "domain_render_required",
                "whatsapp_fast_path",
            ],
        }

    def domain_states(self) -> list[DomainPolicyState]:
        return sorted(self._domain_state.values(), key=lambda item: item.pages_seen, reverse=True)

    def _state_for(self, host: str, candidate: URLCandidate) -> DomainPolicyState:
        state = self._domain_state.get(host)
        if state:
            return state
        state = DomainPolicyState(
            domain=host,
            extraction_confidence_avg=candidate.last_extraction_confidence,
            domain_yield_rate=candidate.domain_yield_rate,
            domain_render_required=candidate.domain_render_required,
            domain_ban_rate=candidate.domain_ban_rate,
        )
        self._domain_state[host] = state
        return state

    def _method_from_confidence(self, confidence: float, llm_enabled: bool) -> ExtractionMethod:
        if confidence > 0.92:
            return ExtractionMethod.css
        if confidence < 0.40 and llm_enabled:
            return ExtractionMethod.llm
        if confidence < 0.75:
            return ExtractionMethod.dom_fingerprint
        return ExtractionMethod.css

    def _requires_render(self, candidate: URLCandidate, state: DomainPolicyState) -> bool:
        url = candidate.url.lower()
        return (
            candidate.domain_render_required
            or state.domain_render_required
            or any(marker in url for marker in self.js_heavy_hosts)
            or self._has_js_framework(candidate)
            or candidate.js_complexity_score >= 0.65
        )

    def _has_js_framework(self, candidate: URLCandidate) -> bool:
        markers = " ".join(
            str(candidate.metadata.get(key, ""))
            for key in ["html_markers", "framework", "scripts"]
        ).lower()
        return any(marker in markers for marker in self.js_framework_markers)

    def _tier_for_score(self, score: float) -> FrontierTier:
        if score >= 0.86:
            return FrontierTier.critical
        if score >= 0.68:
            return FrontierTier.high
        if score >= 0.42:
            return FrontierTier.medium
        if score >= 0.20:
            return FrontierTier.low
        return FrontierTier.deferred

    def _path_depth(self, path: str) -> int:
        return len([part for part in path.split("/") if part])

    def _moving_average(self, old: float, new: float, weight: float) -> float:
        return round(max(0.0, min(1.0, old * (1 - weight) + new * weight)), 4)
