"""Unit tests for the anti-bot escalation ladder.

The ladder is pure decision logic, so these tests need no network or browser
(testing-standards SKILL: mock externals, test edge cases).
"""

from __future__ import annotations

from asagus.layers.escalation import (
    EscalationLadder,
    EscalationStep,
    StepPlan,
    is_blocked,
    plan_for_step,
)
from asagus.models import ProxyTier


def _steps(ladder: EscalationLadder) -> list[str]:
    return [plan.label for plan in ladder]


def test_full_ladder_order_when_everything_available() -> None:
    ladder = EscalationLadder(
        start_step=EscalationStep.static,
        max_step=EscalationStep.stealth_session,
        has_saved_session=False,
        stealth_available=True,
    )
    assert _steps(ladder) == ["static", "dynamic", "stealth", "stealth_session"]


def test_saved_session_jumps_to_session_reuse_first() -> None:
    ladder = EscalationLadder(
        has_saved_session=True,
        stealth_available=True,
    )
    # With a cleared session in hand we go straight to reusing it.
    assert _steps(ladder) == ["stealth_session"]


def test_stealth_rungs_skipped_when_no_stealth_engine() -> None:
    ladder = EscalationLadder(
        start_step=EscalationStep.static,
        max_step=EscalationStep.stealth_session,
        has_saved_session=False,
        stealth_available=False,
    )
    # Only non-stealth rungs survive.
    assert _steps(ladder) == ["static", "dynamic"]


def test_start_step_respects_dynamic_policy() -> None:
    ladder = EscalationLadder(
        start_step=EscalationStep.dynamic,
        max_step=EscalationStep.stealth,
        stealth_available=True,
    )
    assert _steps(ladder) == ["dynamic", "stealth"]


def test_max_step_caps_the_ladder() -> None:
    ladder = EscalationLadder(
        max_step=EscalationStep.dynamic,
        stealth_available=True,
    )
    assert _steps(ladder) == ["static", "dynamic"]


def test_plan_for_step_proxy_tiers() -> None:
    assert plan_for_step(EscalationStep.static).proxy_tier == ProxyTier.datacenter
    assert plan_for_step(EscalationStep.dynamic).proxy_tier == ProxyTier.datacenter
    assert plan_for_step(EscalationStep.stealth).proxy_tier == ProxyTier.residential
    assert plan_for_step(EscalationStep.stealth_session).proxy_tier == ProxyTier.residential


def test_plan_flags() -> None:
    static = plan_for_step(EscalationStep.static)
    assert static.use_browser is False
    session = plan_for_step(EscalationStep.stealth_session)
    assert isinstance(session, StepPlan)
    assert session.use_browser and session.prefer_stealth_engine and session.use_saved_session


def test_is_blocked_detects_challenge() -> None:
    assert is_blocked(200, challenge_detected=True, html="<html>full page</html>" * 50) is True


def test_is_blocked_detects_block_status() -> None:
    assert is_blocked(403, challenge_detected=False, html="x" * 500) is True
    assert is_blocked(429, challenge_detected=False, html="x" * 500) is True


def test_is_blocked_detects_empty_body() -> None:
    assert is_blocked(200, challenge_detected=False, html="   ") is True


def test_is_blocked_accepts_good_page() -> None:
    assert is_blocked(200, challenge_detected=False, html="<html>" + "content " * 100 + "</html>") is False
