"""Anti-bot escalation ladder.

Instead of routing a blocked/challenged page straight to manual review, we
climb a ladder of progressively stronger (and costlier) fetch strategies and
only give up at the top. This is the core of the *avoidance* approach: most
challenges disappear once you present as a real browser from a residential IP
and reuse a previously-cleared session.

The ladder is intentionally a *pure* decision structure (no I/O), so it can
be unit-tested in isolation per the testing-standards SKILL. The FetchLayer
owns the actual execution of each step.

Ladder (low -> high cost):
    0. static          - curl-cffi / httpx static fetch
    1. dynamic         - plain Playwright Chromium render
    2. stealth         - patchright / camoufox, residential proxy
    3. stealth_session - stealth engine + reuse stored clearance cookies
    -> manual_review   - exhausted; flag for a human
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from asagus.models import ProxyTier


class EscalationStep(IntEnum):
    """Ordered rungs of the escalation ladder."""

    static = 0
    dynamic = 1
    stealth = 2
    stealth_session = 3


# Human-readable labels used in logs / telemetry.
STEP_LABELS: dict[EscalationStep, str] = {
    EscalationStep.static: "static",
    EscalationStep.dynamic: "dynamic",
    EscalationStep.stealth: "stealth",
    EscalationStep.stealth_session: "stealth_session",
}

# HTTP statuses that indicate a soft/hard block worth escalating on.
BLOCK_STATUS_CODES = frozenset({401, 403, 405, 406, 429, 503})


@dataclass(frozen=True)
class StepPlan:
    """Concrete instructions for executing one rung of the ladder.

    Attributes:
        step: Which rung this plan represents.
        use_browser: Whether a browser render is required (vs static fetch).
        prefer_stealth_engine: Prefer patchright/camoufox over plain Chromium.
        use_saved_session: Reuse stored clearance cookies for the domain.
        proxy_tier: Proxy tier to request for this attempt.
        label: Human-readable name.
    """

    step: EscalationStep
    use_browser: bool
    prefer_stealth_engine: bool
    use_saved_session: bool
    proxy_tier: ProxyTier
    label: str


def plan_for_step(step: EscalationStep) -> StepPlan:
    """Return the concrete :class:`StepPlan` for a ladder rung."""
    if step == EscalationStep.static:
        return StepPlan(step, False, False, False, ProxyTier.datacenter, "static")
    if step == EscalationStep.dynamic:
        return StepPlan(step, True, False, False, ProxyTier.datacenter, "dynamic")
    if step == EscalationStep.stealth:
        return StepPlan(step, True, True, False, ProxyTier.residential, "stealth")
    return StepPlan(step, True, True, True, ProxyTier.residential, "stealth_session")


def is_blocked(status_code: int, challenge_detected: bool, html: str) -> bool:
    """Decide whether a fetch result represents a block/challenge.

    Args:
        status_code: HTTP status from the fetch.
        challenge_detected: Output of the challenge detector for the page.
        html: Returned HTML (empty/short bodies on a block are suspicious).

    Returns:
        True if we should escalate rather than accept this result.
    """
    if challenge_detected:
        return True
    if status_code in BLOCK_STATUS_CODES:
        return True
    # A 200 with no usable body is a common silent block.
    if status_code in {0, 200} and len(html.strip()) < 200:
        return True
    return False


class EscalationLadder:
    """Stateful per-attempt ladder walker for a single candidate fetch.

    Usage::

        ladder = EscalationLadder(max_step=EscalationStep.stealth_session,
                                  has_saved_session=store_has_cookies,
                                  stealth_available=engine_available)
        for plan in ladder:
            result = await execute(plan)
            if not is_blocked(...):
                break
    """

    def __init__(
        self,
        *,
        start_step: EscalationStep = EscalationStep.static,
        max_step: EscalationStep = EscalationStep.stealth_session,
        has_saved_session: bool = False,
        stealth_available: bool = True,
    ) -> None:
        self.max_step = max_step
        self.stealth_available = stealth_available
        self.has_saved_session = has_saved_session
        # If we already hold a cleared session, jump straight to reusing it,
        # but never below the requested start step.
        if has_saved_session and stealth_available:
            self._next = max(start_step, EscalationStep.stealth_session)
        else:
            self._next = start_step
        self._exhausted = False

    def __iter__(self) -> "EscalationLadder":
        return self

    def __next__(self) -> StepPlan:
        if self._exhausted:
            raise StopIteration
        step = self._next
        # Skip stealth rungs when no stealth engine is available.
        while step in {EscalationStep.stealth, EscalationStep.stealth_session} and not self.stealth_available:
            if step >= self.max_step:
                self._exhausted = True
                raise StopIteration
            step = EscalationStep(step + 1)
        if step > self.max_step:
            self._exhausted = True
            raise StopIteration
        # Advance for the following call.
        if step >= self.max_step:
            self._exhausted = True
        else:
            self._next = EscalationStep(step + 1)
        return plan_for_step(step)
