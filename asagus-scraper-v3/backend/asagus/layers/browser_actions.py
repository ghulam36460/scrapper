"""Browser action DSL for Deep Agent Mode workflows."""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from asagus.models import utc_now


class BrowserActionType(str, Enum):
    navigate = "navigate"
    click = "click"
    fill = "fill"
    select = "select"
    type = "type"
    wait_for_selector = "wait_for_selector"
    wait_for_navigation = "wait_for_navigation"
    screenshot = "screenshot"
    extract_text = "extract_text"
    extract_table = "extract_table"
    extract_json = "extract_json"
    evaluate_js = "evaluate_js"
    set_viewport = "set_viewport"
    scroll = "scroll"
    keyboard = "keyboard"
    mouse_move = "mouse_move"
    human_pause = "human_pause"


class BrowserAction(BaseModel):
    """Typed browser action for workflow."""

    action: BrowserActionType
    url: Optional[str] = None
    selector: Optional[str] = None
    value: Optional[str] = None
    timeout_ms: int = 30000
    xpath: Optional[str] = None
    code: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    direction: Optional[str] = None
    key: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    duration_ms: Optional[int] = None
    human_like: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class BrowserActionResult(BaseModel):
    """Result of browser action execution."""

    action: BrowserActionType
    success: bool
    timestamp: str
    result: Any = None
    error: Optional[str] = None
    duration_ms: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class BrowserActionExecutor:
    """Execute browser actions with human-like behavior."""

    def __init__(self, page, human_behavior=None):
        self.page = page
        self.human_behavior = human_behavior
        self.trace: list[BrowserActionResult] = []
        self.action_budget = 20

    async def execute_action(self, action: BrowserAction) -> BrowserActionResult:
        """Execute a single browser action."""
        from asagus.layers.human_behavior import HumanBehavior

        validation_error = self._validate_action(action)
        if validation_error:
            result = BrowserActionResult(
                action=action.action,
                success=False,
                timestamp=utc_now().isoformat(),
                result=None,
                error=validation_error,
                duration_ms=0,
                metadata=action.metadata,
            )
            self.trace.append(result)
            return result

        if not self.human_behavior and action.human_like:
            self.human_behavior = HumanBehavior()

        start_time = time.time()
        success = False
        result = None
        error = None

        try:
            if action.action == BrowserActionType.navigate:
                await self.page.goto(action.url, timeout=action.timeout_ms)
                success = True

            elif action.action == BrowserActionType.click:
                if action.human_like and self.human_behavior:
                    box = await self.page.query_selector(action.selector)
                    if box:
                        bbox = await box.bounding_box()
                        if bbox:
                            await self.human_behavior.click(
                                self.page,
                                bbox["x"] + bbox["width"] / 2,
                                bbox["y"] + bbox["height"] / 2,
                            )
                    else:
                        await self.page.click(action.selector)
                else:
                    await self.page.click(action.selector)
                success = True

            elif action.action == BrowserActionType.fill:
                await self.page.fill(action.selector, action.value or "")
                success = True

            elif action.action == BrowserActionType.type:
                if action.human_like and self.human_behavior:
                    await self.human_behavior.type_text(
                        self.page,
                        action.selector,
                        action.value or "",
                    )
                else:
                    await self.page.type(action.selector, action.value or "")
                success = True

            elif action.action == BrowserActionType.select:
                await self.page.select_option(action.selector, action.value or "")
                success = True

            elif action.action == BrowserActionType.wait_for_selector:
                await self.page.wait_for_selector(
                    action.selector,
                    timeout=action.timeout_ms
                )
                success = True

            elif action.action == BrowserActionType.screenshot:
                result = await self.page.screenshot(path=action.value)
                success = True

            elif action.action == BrowserActionType.extract_text:
                elements = await self.page.query_selector_all(action.selector)
                result = [await e.text_content() for e in elements]
                success = True

            elif action.action == BrowserActionType.extract_table:
                result = await self.page.evaluate(f"""
                    () => {{
                        const table = document.querySelector('{action.selector}');
                        const rows = [];
                        table.querySelectorAll('tr').forEach(tr => {{
                            const cells = [];
                            tr.querySelectorAll('td,th').forEach(td => cells.push(td.textContent));
                            rows.push(cells);
                        }});
                        return rows;
                    }}
                """)
                success = True

            elif action.action == BrowserActionType.evaluate_js:
                result = await self.page.evaluate(action.code or "() => null")
                success = True

            elif action.action == BrowserActionType.scroll:
                direction = action.direction or "down"
                if action.human_like and self.human_behavior:
                    await self.human_behavior.scroll(self.page, direction)
                else:
                    amount = 300 if direction == "down" else -300
                    await self.page.evaluate(f"() => window.scrollBy(0, {amount})")
                success = True

            elif action.action == BrowserActionType.human_pause:
                duration_ms = action.duration_ms or 500
                if self.human_behavior:
                    await self.human_behavior.random_idle(
                        int(duration_ms * 0.5),
                        int(duration_ms)
                    )
                success = True

            elif action.action == BrowserActionType.set_viewport:
                await self.page.set_viewport_size({
                    "width": action.width or 1365,
                    "height": action.height or 900
                })
                success = True

            elif action.action == BrowserActionType.keyboard:
                await self.page.keyboard.press(action.key or "Enter")
                success = True

            elif action.action == BrowserActionType.mouse_move:
                await self.page.mouse.move(int(action.x or 0), int(action.y or 0))
                success = True

        except Exception as e:
            success = False
            error = str(e)

        duration_ms = (time.time() - start_time) * 1000

        action_result = BrowserActionResult(
            action=action.action,
            success=success,
            timestamp=utc_now().isoformat(),
            result=result,
            error=error,
            duration_ms=duration_ms,
            metadata=action.metadata,
        )

        self.trace.append(action_result)

        if len(self.trace) >= self.action_budget:
            raise RuntimeError(f"Action budget exceeded: {self.action_budget}")

        return action_result

    def _validate_action(self, action: BrowserAction) -> str:
        selector_actions = {
            BrowserActionType.click,
            BrowserActionType.fill,
            BrowserActionType.select,
            BrowserActionType.type,
            BrowserActionType.wait_for_selector,
            BrowserActionType.extract_text,
            BrowserActionType.extract_table,
        }
        if action.action == BrowserActionType.navigate and not action.url:
            return "navigate action requires url"
        if action.action in selector_actions and not action.selector:
            return f"{action.action.value} action requires selector"
        if action.action == BrowserActionType.evaluate_js and not action.code:
            return "evaluate_js action requires code"
        if action.action == BrowserActionType.keyboard and not action.key:
            return "keyboard action requires key"
        return ""

    async def execute_workflow(self, actions: list[BrowserAction]) -> list[BrowserActionResult]:
        """Execute workflow of actions."""
        results = []
        for action in actions:
            result = await self.execute_action(action)
            results.append(result)
            if not result.success:
                break
        return results

    def get_trace(self) -> list[dict]:
        """Get execution trace for debugging/replay."""
        return [r.model_dump() for r in self.trace]

    def state(self) -> dict[str, object]:
        return {
            "purpose": "Execute complex browser workflows with human-like interaction",
            "supported_actions": [a.value for a in BrowserActionType],
            "action_budget": self.action_budget,
            "trace_enabled": True,
            "human_like_behavior": self.human_behavior is not None,
        }
