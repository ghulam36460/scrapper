"""Human-like behavior simulation for evading behavioral biometrics."""

from __future__ import annotations

import asyncio
import math
import random
from typing import Tuple


class WindMouse:
    """
    Physics-based mouse movement simulation.
    Reference: https://github.com/AsfhtgkDavid/windmouse
    
    Simulates realistic mouse movement using gravity, wind, and randomness
    to evade behavioral detection systems.
    """

    def __init__(self, G_0: float = 9.81, drift: float = 3.5, noise_scale: float = 1.5):
        """
        G_0: gravitational constant (higher = more gravity effect)
        drift: wind effect strength (higher = more curved)
        noise_scale: randomness scale (higher = more jittery)
        """
        self.G_0 = G_0
        self.drift = drift
        self.noise_scale = noise_scale

    def calculate_trajectory(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        duration_ms: int = 500,
    ) -> list[Tuple[float, float]]:
        """Calculate realistic mouse trajectory from start to end."""
        distance = math.sqrt((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2)
        
        if distance < 100:
            duration = max(100, min(duration_ms, 300))
        elif distance < 500:
            duration = max(150, min(duration_ms, 600))
        else:
            duration = min(duration_ms, 1000)

        dt = 0.01
        total_steps = int(duration / (dt * 1000))
        trajectory = [start]

        wind_start = random.uniform(self.drift * 0.5, self.drift)
        wind_end = random.uniform(self.drift * 0.5, self.drift)

        x, y = float(start[0]), float(start[1])
        vx, vy = 0.0, 0.0

        for step in range(1, total_steps):
            progress = step / total_steps
            
            target_x = end[0] + random.gauss(0, 10)
            target_y = end[1] + random.gauss(0, 10)

            wind = wind_start + (wind_end - wind_start) * progress

            ax = (target_x - x) / max(distance, 1) * self.G_0 + random.gauss(0, self.noise_scale)
            ay = (target_y - y) / max(distance, 1) * self.G_0 + random.gauss(0, self.noise_scale)

            vx += ax * dt + wind * random.gauss(0, 1) * dt
            vy += ay * dt + wind * random.gauss(0, 1) * dt

            vx *= 0.98
            vy *= 0.98

            x += vx * dt * 100
            y += vy * dt * 100

            trajectory.append((x, y))

        trajectory.append(end)
        return trajectory


class HumanBehavior:
    """
    Simulate human-like interaction patterns.
    Reference: https://github.com/riflosnake/HumanCursor
    """

    def __init__(self, typing_variance: float = 0.15, pause_frequency: float = 0.1):
        self.windmouse = WindMouse()
        self.typing_variance = typing_variance
        self.pause_frequency = pause_frequency

    async def move_mouse(
        self,
        page,
        from_pos: Tuple[float, float],
        to_pos: Tuple[float, float],
        duration_ms: int = 500,
    ) -> None:
        """Simulate realistic mouse movement via Playwright."""
        trajectory = self.windmouse.calculate_trajectory(from_pos, to_pos, duration_ms)

        for i in range(1, len(trajectory)):
            x, y = trajectory[i]
            await page.mouse.move(int(x), int(y))
            await asyncio.sleep(0.01)

    async def click(
        self,
        page,
        x: float,
        y: float,
        button: str = "left",
        delay_ms: int = 50,
        move_first: bool = True,
    ) -> None:
        """Simulate human-like click with mouse movement."""
        if move_first:
            current_pos = (0, 0)
            await self.move_mouse(page, current_pos, (x, y))

        pre_click_delay = random.uniform(delay_ms * 0.5, delay_ms * 1.5) / 1000
        await asyncio.sleep(pre_click_delay)

        await page.mouse.click(x, y, button=button)

        post_click_delay = random.uniform(50, 200) / 1000
        await asyncio.sleep(post_click_delay)

    async def type_text(
        self,
        page,
        selector: str,
        text: str,
        delay_ms: int = 100,
    ) -> None:
        """Type text with human-like timing."""
        await page.click(selector)
        await asyncio.sleep(random.uniform(100, 300) / 1000)

        for char in text:
            char_delay = delay_ms * random.uniform(
                1 - self.typing_variance,
                1 + self.typing_variance
            )

            if random.random() < self.pause_frequency:
                await asyncio.sleep(random.uniform(200, 500) / 1000)

            await page.type(selector, char, delay=int(char_delay))

    async def scroll(
        self,
        page,
        direction: str = "down",
        steps: int = 3,
        delay_between_steps_ms: int = 200,
    ) -> None:
        """Simulate human-like scrolling."""
        for _ in range(steps):
            amount = 300 if direction == "down" else -300
            await page.evaluate(f"() => window.scrollBy(0, {amount})")
            await asyncio.sleep(
                random.uniform(delay_between_steps_ms * 0.5, delay_between_steps_ms * 1.5) / 1000
            )

    async def random_idle(self, min_ms: int = 100, max_ms: int = 500) -> None:
        """Random idle period (thinking/looking at content)."""
        delay = random.uniform(min_ms, max_ms) / 1000
        await asyncio.sleep(delay)

    def state(self) -> dict[str, object]:
        return {
            "algorithms": ["windmouse_physics", "human_typing_variance", "scroll_smoothing"],
            "features": [
                "realistic_mouse_trajectories",
                "variable_typing_speed",
                "random_interaction_delays",
                "smooth_scrolling",
                "random_idle_periods",
            ],
            "purpose": "Evade behavioral biometrics detection in bot challenges",
        }
