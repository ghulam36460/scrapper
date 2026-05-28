from __future__ import annotations

from collections import Counter, defaultdict
from math import log, sqrt
from typing import ClassVar
from urllib.parse import quote_plus, urlparse

from asagus.models import (
    FrontierTier,
    MDPAction,
    MDPDecision,
    MDPPhase,
    MDPState,
    URLCandidate,
    URLType,
)


Outcome = str
StateKey = str


TRANSITION_PRIORS: dict[URLType, tuple[float, float, float]] = {
    URLType.maps_listing_url: (0.91, 0.07, 0.02),
    URLType.maps_search_grid: (0.91, 0.07, 0.02),
    URLType.website_contact: (0.78, 0.18, 0.04),
    URLType.website_about: (0.74, 0.19, 0.07),
    URLType.website_homepage: (0.52, 0.31, 0.17),
    URLType.website_blog_post: (0.04, 0.11, 0.85),
    URLType.website_product: (0.38, 0.42, 0.20),
    URLType.directory_profile: (0.69, 0.23, 0.08),
    URLType.social_profile: (0.43, 0.38, 0.19),
    URLType.unknown: (0.31, 0.28, 0.41),
}

OUTCOMES: tuple[Outcome, ...] = ("full", "partial", "dead", "deferred", "skipped", "banned")
PLANNING_ACTIONS: tuple[MDPAction, ...] = (
    MDPAction.crawl_now,
    MDPAction.defer_1h,
    MDPAction.defer_24h,
    MDPAction.skip,
    MDPAction.prioritize_up,
    MDPAction.prioritize_down,
)


class MDPScheduler:
    """Strong crawl-control MDP.

    This is now action-aware, not just a URL-type score. It builds an abstract
    Markov state space from the document's state vector, estimates transition
    probabilities per action, runs value iteration, and adds online reward
    learning through UCB bonuses.
    """

    _planning_cache: ClassVar[
        dict[tuple[float, int], tuple[dict[StateKey, MDPState], dict[StateKey, float], dict[StateKey, MDPAction]]]
    ] = {}

    def __init__(self, discount: float = 0.86, iterations: int = 48) -> None:
        self.discount = discount
        self.iterations = iterations
        self.crawl_count = 0
        self.action_counts: Counter[str] = Counter()
        self.action_reward_sum: Counter[str] = Counter()
        self.state_action_counts: Counter[str] = Counter()
        self.state_action_reward_sum: Counter[str] = Counter()
        self.outcome_counts: dict[str, Counter[str]] = defaultdict(Counter)
        cache_key = (discount, iterations)
        cached = self._planning_cache.get(cache_key)
        if cached:
            self.state_space, self.state_values, self.policy_table = cached
        else:
            self.state_space = self.generate_state_space()
            self.state_values: dict[StateKey, float] = {}
            self.policy_table: dict[StateKey, MDPAction] = {}
            self.value_iteration()
            self._planning_cache[cache_key] = (self.state_space, self.state_values, self.policy_table)

    def decide(self, candidate: URLCandidate) -> MDPDecision:
        state = self.state_from_candidate(candidate)
        state_key = self.bucket_state(state)
        phase = self.phase_for_count(self.crawl_count)
        epsilon = self.epsilon_for_phase(phase)
        expected_yield = self.expected_yield(state)
        heuristic_score = self.heuristic_score(candidate, state)
        q_values = self.q_values(state, phase, heuristic_score)
        action = self.select_action(q_values, phase, state)
        transition_probs = self.action_transition(state, action)
        selected_score = q_values[action]
        reward_estimate = sum(
            probability * self.reward(state, action, outcome)
            for outcome, probability in transition_probs.items()
        )
        tier = self.tier_for_score(selected_score, action)
        strategy = self.strategy_for(candidate)
        self.action_counts[action.value] += 1
        self.crawl_count += 1

        return MDPDecision(
            state=state,
            state_key=state_key,
            action=action,
            phase=phase,
            epsilon=epsilon,
            frontier_tier=tier,
            expected_yield=round(expected_yield, 3),
            reward_estimate=round(reward_estimate, 3),
            selected_score=round(selected_score, 4),
            q_values={item.value: round(score, 4) for item, score in q_values.items()},
            transition_probs={key: round(value, 4) for key, value in transition_probs.items()},
            strategy=strategy,
            reasons=[
                f"phase={phase.value}",
                f"state_key={state_key}",
                f"policy_action={action.value}",
                f"strategy={strategy}",
                f"transition_prior={TRANSITION_PRIORS.get(state.url_type, TRANSITION_PRIORS[URLType.unknown])}",
                f"value={self.state_values.get(state_key, 0):.4f}",
                f"ucb={self.ucb_bonus(state_key, action):.4f}",
            ],
        )

    def state_from_candidate(self, candidate: URLCandidate) -> MDPState:
        url_type = candidate.url_type
        if url_type == URLType.unknown:
            url_type = self.infer_url_type(candidate)
        return MDPState(
            url_path_depth=self.path_depth(candidate.url),
            url_type=url_type,
            domain_yield_rate=candidate.domain_yield_rate,
            domain_render_required=candidate.domain_render_required,
            domain_ban_rate=candidate.domain_ban_rate,
            parent_page_yield=candidate.parent_page_yield,
            time_in_frontier_h=candidate.time_in_frontier_h,
            link_density=candidate.link_density,
            js_complexity_score=candidate.js_complexity_score,
            last_extraction_conf=candidate.last_extraction_confidence,
        )

    def annotate(self, candidate: URLCandidate) -> tuple[URLCandidate, MDPDecision]:
        decision = self.decide(candidate)
        candidate.frontier_tier = decision.frontier_tier
        candidate.url_type = decision.state.url_type
        candidate.priority = self.priority_from_decision(candidate.priority, decision)
        candidate.metadata["mdp_decision"] = decision.model_dump(mode="json")
        return candidate, decision

    def q_values(self, state: MDPState, phase: MDPPhase, heuristic_score: float = 0.0) -> dict[MDPAction, float]:
        state_key = self.bucket_state(state)
        values: dict[MDPAction, float] = {}
        for action in PLANNING_ACTIONS:
            transition = self.action_transition(state, action)
            expected = 0.0
            for outcome, probability in transition.items():
                immediate = self.reward(state, action, outcome)
                next_key = self.next_state_key(state, action, outcome)
                expected += probability * (immediate + self.discount * self.state_values.get(next_key, 0.0))
            expected += self.learned_reward_adjustment(state_key, action)
            expected += self.ucb_bonus(state_key, action)
            if phase == MDPPhase.heuristic_a:
                expected = expected * 0.35 + self.action_prior_score(action, heuristic_score) * 0.65
            elif phase == MDPPhase.hybrid_b:
                expected = expected * 0.70 + self.action_prior_score(action, heuristic_score) * 0.30
            values[action] = expected
        return values

    def select_action(self, q_values: dict[MDPAction, float], phase: MDPPhase, state: MDPState) -> MDPAction:
        if state.domain_ban_rate >= 0.80:
            return MDPAction.defer_24h
        if phase == MDPPhase.heuristic_a:
            # Phase A keeps exploration high but still prevents obviously bad work.
            return max(q_values, key=q_values.get)
        if phase == MDPPhase.hybrid_b and state.domain_ban_rate >= 0.45:
            return MDPAction.defer_1h
        return max(q_values, key=q_values.get)

    def action_transition(self, state: MDPState, action: MDPAction) -> dict[Outcome, float]:
        full, partial, dead = self.adjusted_base_prior(state)

        if action == MDPAction.skip:
            return {"skipped": 0.96, "dead": 0.04}
        if action == MDPAction.defer_24h:
            deferred = 0.72
            improved = self._normalize({"full": full * 1.08, "partial": partial * 1.02, "dead": dead * 0.86})
            return self._mix({"deferred": deferred}, improved, 1 - deferred)
        if action == MDPAction.defer_1h:
            deferred = 0.42
            improved = self._normalize({"full": full * 1.03, "partial": partial * 1.01, "dead": dead * 0.94})
            return self._mix({"deferred": deferred}, improved, 1 - deferred)

        render_bonus = 1.10 if state.domain_render_required or state.js_complexity_score >= 0.65 else 1.0
        if action == MDPAction.prioritize_up:
            raw = {"full": full * 1.07 * render_bonus, "partial": partial * 1.03, "dead": dead * 0.92}
        elif action == MDPAction.prioritize_down:
            raw = {"full": full * 0.82, "partial": partial * 1.06, "dead": dead * 1.10}
        else:
            raw = {"full": full * render_bonus, "partial": partial, "dead": dead}

        banned = min(0.30, state.domain_ban_rate * (0.55 if action == MDPAction.prioritize_up else 0.40))
        normalized = self._normalize(raw)
        return self._mix({"banned": banned}, normalized, 1 - banned)

    def adjusted_base_prior(self, state: MDPState) -> tuple[float, float, float]:
        full, partial, dead = TRANSITION_PRIORS.get(state.url_type, TRANSITION_PRIORS[URLType.unknown])
        depth_penalty = min(state.url_path_depth * 0.06, 0.30)
        yield_boost = (state.domain_yield_rate - 0.5) * 0.22
        parent_boost = (state.parent_page_yield - 0.5) * 0.14
        confidence_boost = (state.last_extraction_conf - 0.5) * 0.18
        ban_penalty = state.domain_ban_rate * 0.36
        js_penalty = max(0.0, state.js_complexity_score - 0.70) * 0.12

        full = max(0.01, full + yield_boost + parent_boost + confidence_boost - depth_penalty - ban_penalty)
        partial = max(0.01, partial + depth_penalty * 0.35 + js_penalty)
        dead = max(0.01, dead + depth_penalty * 0.65 + ban_penalty + js_penalty - yield_boost * 0.35)
        normalized = self._normalize({"full": full, "partial": partial, "dead": dead})
        return normalized["full"], normalized["partial"], normalized["dead"]

    def reward(self, state: MDPState, action: MDPAction, outcome: Outcome) -> float:
        render_cost = 0.22 if state.domain_render_required else 0.05
        proxy_cost = 0.12 if state.domain_ban_rate > 0.25 else 0.03
        time_cost = {
            MDPAction.crawl_now: 0.04,
            MDPAction.prioritize_up: 0.08,
            MDPAction.prioritize_down: 0.025,
            MDPAction.defer_1h: 0.015,
            MDPAction.defer_24h: 0.03,
            MDPAction.skip: 0.0,
        }[action]
        opportunity_cost = self.expected_yield(state) * (0.45 if action == MDPAction.skip else 0.0)
        cost = render_cost + proxy_cost + time_cost + opportunity_cost
        if outcome == "full":
            return 2.4 + state.last_extraction_conf * 0.9 + state.domain_yield_rate * 0.7 - cost
        if outcome == "partial":
            return 0.85 + state.last_extraction_conf * 0.35 - cost * 0.8
        if outcome == "dead":
            return -0.35 - cost
        if outcome == "banned":
            return -1.8 - cost * 1.4
        if outcome == "deferred":
            return -0.03 - time_cost
        if outcome == "skipped":
            return -opportunity_cost
        return 0.0

    def value_iteration(self) -> None:
        values = {state_key: 0.0 for state_key in self.state_space}
        policy: dict[StateKey, MDPAction] = {}
        transitions: dict[tuple[StateKey, MDPAction], list[tuple[float, float, StateKey]]] = {}
        for state_key, state in self.state_space.items():
            for action in PLANNING_ACTIONS:
                transitions[(state_key, action)] = [
                    (probability, self.reward(state, action, outcome), self.next_state_key(state, action, outcome))
                    for outcome, probability in self.action_transition(state, action).items()
                ]
        for _ in range(self.iterations):
            updated: dict[StateKey, float] = {}
            for state_key in self.state_space:
                action_values = {}
                for action in PLANNING_ACTIONS:
                    action_values[action] = sum(
                        probability * (reward + self.discount * values.get(next_key, 0.0))
                        for probability, reward, next_key in transitions[(state_key, action)]
                    )
                best_action = max(action_values, key=action_values.get)
                updated[state_key] = action_values[best_action]
                policy[state_key] = best_action
            values = updated
        self.state_values = values
        self.policy_table = policy

    def record_reward(
        self,
        action: MDPAction,
        reward: float,
        state_key: str = "",
        outcome: Outcome = "partial",
    ) -> None:
        action_key = action.value
        state_action_key = self._state_action_key(state_key, action)
        self.action_counts[action_key] += 1
        self.action_reward_sum[action_key] += reward
        self.state_action_counts[state_action_key] += 1
        self.state_action_reward_sum[state_action_key] += reward
        self.outcome_counts[state_action_key][outcome] += 1

    def learned_reward_adjustment(self, state_key: StateKey, action: MDPAction) -> float:
        key = self._state_action_key(state_key, action)
        count = self.state_action_counts[key]
        if count:
            return max(-0.7, min(0.7, (self.state_action_reward_sum[key] / count) * 0.12))
        action_count = self.action_counts[action.value]
        if action_count:
            return max(-0.4, min(0.4, (self.action_reward_sum[action.value] / action_count) * 0.08))
        return 0.0

    def ucb_bonus(self, state_key: StateKey, action: MDPAction) -> float:
        total = max(sum(self.state_action_counts.values()) + sum(self.action_counts.values()), 1)
        state_action_count = self.state_action_counts[self._state_action_key(state_key, action)]
        action_count = self.action_counts[action.value]
        count = max(state_action_count or action_count, 1)
        mean_reward = 0.0
        if state_action_count:
            mean_reward = self.state_action_reward_sum[self._state_action_key(state_key, action)] / state_action_count
        elif action_count:
            mean_reward = self.action_reward_sum[action.value] / action_count
        return max(0.0, min(0.55, mean_reward * 0.03 + sqrt(2 * log(total + 1) / count) * 0.08))

    def phase_for_count(self, crawl_count: int) -> MDPPhase:
        if crawl_count < 200:
            return MDPPhase.heuristic_a
        if crawl_count < 1000:
            return MDPPhase.hybrid_b
        return MDPPhase.learned_c

    def epsilon_for_phase(self, phase: MDPPhase) -> float:
        if phase == MDPPhase.heuristic_a:
            return 1.0
        if phase == MDPPhase.hybrid_b:
            return 0.30
        return 0.05

    def expected_yield(self, state: MDPState) -> float:
        full, partial, _dead = self.adjusted_base_prior(state)
        return max(0.0, min(1.0, full + partial * 0.45))

    def heuristic_score(self, candidate: URLCandidate, state: MDPState) -> float:
        url = candidate.url.lower()
        path_bonus = 0.16 if any(token in url for token in ["contact", "about", "reach-us", "maps/search"]) else 0.0
        link_bonus = min(state.link_density * 0.10, 0.10)
        depth_penalty = min(state.url_path_depth * 0.07, 0.32)
        ban_penalty = state.domain_ban_rate * 0.25
        value = (
            candidate.priority * 0.30
            + state.domain_yield_rate * 0.30
            + state.parent_page_yield * 0.15
            + state.last_extraction_conf * 0.15
            + path_bonus
            + link_bonus
            - depth_penalty
            - ban_penalty
        )
        return max(0.0, min(1.0, value))

    def reward_estimate(
        self,
        data_fields_extracted: float,
        completeness_score: float,
        render_time_ms: int,
        proxy_cost: float,
    ) -> float:
        cost_penalty = (render_time_ms / 1000) * proxy_cost
        return data_fields_extracted * completeness_score - cost_penalty

    def action_prior_score(self, action: MDPAction, heuristic_score: float) -> float:
        if action == MDPAction.prioritize_up:
            return heuristic_score + 0.10
        if action == MDPAction.crawl_now:
            return heuristic_score
        if action == MDPAction.defer_1h:
            return heuristic_score * 0.62
        if action == MDPAction.defer_24h:
            return heuristic_score * 0.44
        if action == MDPAction.prioritize_down:
            return heuristic_score * 0.50
        return 0.12 if heuristic_score < 0.20 else -0.20

    def next_state_key(self, state: MDPState, action: MDPAction, outcome: Outcome) -> StateKey:
        next_state = state.model_copy(deep=True)
        if outcome == "full":
            next_state.url_type = URLType.website_contact
            next_state.domain_yield_rate = min(1.0, state.domain_yield_rate + 0.18)
            next_state.last_extraction_conf = min(1.0, state.last_extraction_conf + 0.16)
            next_state.domain_ban_rate = max(0.0, state.domain_ban_rate - 0.06)
        elif outcome == "partial":
            next_state.url_type = URLType.website_homepage
            next_state.domain_yield_rate = min(1.0, state.domain_yield_rate + 0.06)
            next_state.last_extraction_conf = min(1.0, state.last_extraction_conf + 0.04)
        elif outcome == "dead":
            next_state.url_type = URLType.website_blog_post
            next_state.domain_yield_rate = max(0.0, state.domain_yield_rate - 0.12)
            next_state.last_extraction_conf = max(0.0, state.last_extraction_conf - 0.12)
        elif outcome == "banned":
            next_state.domain_ban_rate = min(1.0, state.domain_ban_rate + 0.35)
            next_state.domain_yield_rate = max(0.0, state.domain_yield_rate - 0.20)
        elif outcome == "deferred":
            next_state.time_in_frontier_h = min(72, state.time_in_frontier_h + (24 if action == MDPAction.defer_24h else 1))
            next_state.domain_ban_rate = max(0.0, state.domain_ban_rate - (0.12 if action == MDPAction.defer_24h else 0.04))
        elif outcome == "skipped":
            next_state.domain_yield_rate = max(0.0, state.domain_yield_rate - 0.02)
        return self.bucket_state(next_state)

    def bucket_state(self, state: MDPState) -> StateKey:
        depth = "seed" if state.url_path_depth == 0 else "shallow" if state.url_path_depth <= 2 else "deep"
        yield_band = self.band(state.domain_yield_rate, "yield")
        ban_band = self.band(state.domain_ban_rate, "ban")
        confidence_band = self.band(state.last_extraction_conf, "conf")
        render = "render" if state.domain_render_required or state.js_complexity_score >= 0.65 else "static"
        return "|".join([state.url_type.value, depth, yield_band, ban_band, confidence_band, render])

    def generate_state_space(self) -> dict[StateKey, MDPState]:
        states: dict[StateKey, MDPState] = {}
        for url_type in TRANSITION_PRIORS:
            for depth_name, depth in {"seed": 0, "shallow": 1, "deep": 3}.items():
                for yield_name, yield_rate in {"yield_low": 0.20, "yield_mid": 0.52, "yield_high": 0.82}.items():
                    for ban_name, ban_rate in {"ban_low": 0.04, "ban_mid": 0.28, "ban_high": 0.64}.items():
                        for conf_name, confidence in {"conf_low": 0.25, "conf_mid": 0.58, "conf_high": 0.88}.items():
                            for render_name, render_required in {"static": False, "render": True}.items():
                                state = MDPState(
                                    url_path_depth=depth,
                                    url_type=url_type,
                                    domain_yield_rate=yield_rate,
                                    domain_render_required=render_required,
                                    domain_ban_rate=ban_rate,
                                    parent_page_yield=yield_rate,
                                    time_in_frontier_h=0,
                                    link_density=0.55,
                                    js_complexity_score=0.74 if render_required else 0.18,
                                    last_extraction_conf=confidence,
                                )
                                key = "|".join([url_type.value, depth_name, yield_name, ban_name, conf_name, render_name])
                                states[key] = state
        return states

    def infer_outcome(self, fields_extracted: int, confidence: float, blocked: bool = False) -> Outcome:
        if blocked:
            return "banned"
        if fields_extracted >= 5 and confidence >= 0.70:
            return "full"
        if fields_extracted >= 2 and confidence >= 0.40:
            return "partial"
        return "dead"

    def tier_for_score(self, score: float, action: MDPAction) -> FrontierTier:
        if action == MDPAction.skip:
            return FrontierTier.blocked
        if action in {MDPAction.defer_1h, MDPAction.defer_24h}:
            return FrontierTier.deferred
        if score >= 2.30:
            return FrontierTier.critical
        if score >= 1.50:
            return FrontierTier.high
        if score >= 0.55:
            return FrontierTier.medium
        return FrontierTier.low

    def priority_from_decision(self, current: float, decision: MDPDecision) -> float:
        normalized_score = max(0.0, min(1.0, decision.selected_score / 3.0))
        if decision.action == MDPAction.prioritize_up:
            return min(1.0, max(current + 0.18, normalized_score))
        if decision.action == MDPAction.prioritize_down:
            return max(0.0, min(current - 0.18, normalized_score))
        if decision.action == MDPAction.skip:
            return 0.0
        if decision.action in {MDPAction.defer_1h, MDPAction.defer_24h}:
            return max(0.0, min(current - 0.08, normalized_score))
        return max(current, normalized_score, decision.expected_yield)

    def strategy_for(self, candidate: URLCandidate) -> str:
        if candidate.metadata.get("recrawl"):
            return "pagerank_recrawl"
        if candidate.url_type in {URLType.maps_listing_url, URLType.maps_search_grid} or "google.com/maps" in candidate.url:
            return "maps_bfs"
        if candidate.url_type in {
            URLType.website_contact,
            URLType.website_about,
            URLType.website_homepage,
            URLType.website_product,
        }:
            return "website_dfs"
        return "priority_queue"

    def infer_url_type(self, candidate: URLCandidate) -> URLType:
        url = candidate.url.lower()
        path = urlparse(candidate.url).path.lower()
        if "google.com/maps/search" in url:
            return URLType.maps_search_grid
        if "google.com/maps/place" in url:
            return URLType.maps_listing_url
        if any(token in path for token in ["contact", "reach-us", "reach_us"]):
            return URLType.website_contact
        if "about" in path:
            return URLType.website_about
        if any(token in path for token in ["blog", "news", "article"]):
            return URLType.website_blog_post
        if any(token in path for token in ["product", "service", "menu"]):
            return URLType.website_product
        if path in {"", "/"}:
            return URLType.website_homepage
        return URLType.unknown

    def path_depth(self, url: str) -> int:
        path = urlparse(url).path
        return len([part for part in path.split("/") if part])

    def transition_priors(self) -> dict[str, list[float]]:
        return {key.value: list(value) for key, value in TRANSITION_PRIORS.items()}

    def policy_snapshot(self, limit: int = 24) -> list[dict[str, object]]:
        ranked = sorted(self.state_values.items(), key=lambda item: item[1], reverse=True)[:limit]
        return [
            {
                "state": state_key,
                "value": round(value, 4),
                "best_action": self.policy_table.get(state_key, MDPAction.defer_1h).value,
            }
            for state_key, value in ranked
        ]

    def band(self, value: float, prefix: str) -> str:
        if value < 0.34:
            return f"{prefix}_low"
        if value < 0.67:
            return f"{prefix}_mid"
        return f"{prefix}_high"

    def _normalize(self, values: dict[str, float]) -> dict[str, float]:
        total = sum(max(0.0, value) for value in values.values()) or 1.0
        return {key: max(0.0, value) / total for key, value in values.items()}

    def _mix(self, fixed: dict[str, float], variable: dict[str, float], variable_weight: float) -> dict[str, float]:
        out = dict(fixed)
        for key, value in variable.items():
            out[key] = out.get(key, 0.0) + value * variable_weight
        return self._normalize(out)

    def _state_action_key(self, state_key: str, action: MDPAction) -> str:
        return f"{state_key or 'global'}::{action.value}"


class CrawlControlPlane:
    """Layer 1 crawl control plane: Maps BFS, website DFS and priority queues."""

    def __init__(self, scheduler: MDPScheduler | None = None) -> None:
        self.scheduler = scheduler or MDPScheduler()

    def seed_from_query(self, query: str, location: str, limit: int) -> list[URLCandidate]:
        maps_query = quote_plus(f"{query} {location}")
        base_url = f"https://www.google.com/maps/search/{maps_query}"
        return [
            URLCandidate(
                url=base_url,
                source="maps_seed",
                depth=0,
                priority=0.95,
                page_type="maps_listing_search",
                url_type=URLType.maps_search_grid,
                frontier_tier=FrontierTier.critical,
                domain_yield_rate=0.91,
                parent_page_yield=0.91,
                link_density=0.78,
                js_complexity_score=0.86,
                last_extraction_confidence=0.72,
                metadata={"limit": limit, "query": query, "location": location, "strategy": "maps_bfs"},
            )
        ]

    def schedule(self, candidates: list[URLCandidate]) -> list[URLCandidate]:
        scheduled: list[URLCandidate] = []
        for candidate in candidates:
            annotated, _decision = self.scheduler.annotate(candidate)
            scheduled.append(annotated)
        return sorted(
            scheduled,
            key=lambda item: (
                self._tier_rank(item.frontier_tier),
                item.priority,
                -item.depth,
            ),
            reverse=True,
        )

    def score_url(self, candidate: URLCandidate) -> float:
        decision = self.scheduler.decide(candidate)
        return max(candidate.priority, decision.expected_yield, max(decision.q_values.values() or [0]) / 3.0)

    def algorithm_state(self) -> dict[str, object]:
        return {
            "cold_start_phases": [
                {"phase": "A", "range": "0-200", "policy": "heuristic-guided high exploration", "epsilon": 1.0},
                {"phase": "B", "range": "200-1000", "policy": "hybrid heuristic + MDP Q-values", "epsilon": 0.30},
                {"phase": "C", "range": "1000+", "policy": "action-value MDP + UCB learning", "epsilon": 0.05},
            ],
            "transition_priors": self.scheduler.transition_priors(),
            "state_space_size": len(self.scheduler.state_space),
            "discount": self.scheduler.discount,
            "value_iteration_iterations": self.scheduler.iterations,
            "policy_snapshot": self.scheduler.policy_snapshot(),
            "frontier_tiers": [tier.value for tier in FrontierTier],
            "actions": [action.value for action in MDPAction],
            "outcomes": list(OUTCOMES),
            "action_counts": dict(self.scheduler.action_counts),
            "state_action_counts": dict(self.scheduler.state_action_counts.most_common(12)),
            "bandit": "UCB over state-action reward history",
            "markov_model": "P(outcome | abstract_state, action) with full/partial/dead/deferred/skipped/banned outcomes",
        }

    def _tier_rank(self, tier: FrontierTier) -> int:
        return {
            FrontierTier.blocked: 0,
            FrontierTier.deferred: 1,
            FrontierTier.low: 2,
            FrontierTier.medium: 3,
            FrontierTier.high: 4,
            FrontierTier.critical: 5,
        }[tier]
