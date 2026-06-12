"""
Layer 5: Behavioral Biometrics and Human Movement Simulation
============================================================
Simulate human interaction patterns to defeat behavioral analysis.

Critical Insight from antibot.md:
Modern bot detection records and analyzes:
- Mouse trajectory: Curved paths with natural acceleration/deceleration
- Mouse velocity: Bell-curve distribution (accelerate, peak, decelerate)
- Keyboard typing: Inter-keystroke timing (IKT) varies per bigram
- Typing errors: ~5-10% natural error rate with backspace corrections
- Scroll patterns: Momentum-based deceleration, micro-pauses
- Click precision: Brief hover with slight jitter, not instant
- Time-on-page: Variable, correlated with content length

Mathematical Models:
★ Sigma Log-Normal Model (Plamondon 1989):
  v(t) = Σ Di × [Φ_ln(t; t0i, μi, σi) - Φ_ln(t; t0i, μi + Δμi, σi)]
  
  Where:
  - Di = amplitude of i-th velocity impulse
  - t0i = motor command launch time
  - μi = log-mean parameter (peak timing)
  - σi = log-standard deviation (shape)
  - Result: Statistically realistic trajectories indistinguishable from real humans

★ Fitts' Law (Fitts 1954):
  MT = a + b × log₂(2D / W)
  
  Where:
  - MT = Movement Time (seconds)
  - D = Distance to target
  - W = Target width
  - Implies: Small/distant targets take longer to click than large/close ones

Key Libraries:
★★★ HumanCursor: Natural motion + variable speed/curvature
★★ HumanMoveMouse: Sigma log-normal model on 300 human samples
★★ HumanTyping: Markov Chain-based keystroke model
★ human-cursor-trajectory: Sigma log-normal mathematical model
"""

from __future__ import annotations

import asyncio
import math
import random
import time
from dataclasses import dataclass
from typing import Tuple

import playwright.async_api as pw


@dataclass
class Point:
    """2D point for cursor movement."""
    x: float
    y: float
    
    def distance_to(self, other: Point) -> float:
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)


class SigmaLogNormalModel:
    """
    Sigma log-normal velocity model for human cursor movement.
    Based on Plamondon (1989) and Feher et al. (2012).
    
    Generates cursor trajectories indistinguishable from real human movement
    using superposition of log-normal velocity impulses.
    """
    
    @staticmethod
    def log_normal(t: float, t0: float, mu: float, sigma: float) -> float:
        """
        Log-normal probability density function.
        
        Args:
            t: time (seconds)
            t0: impulse start time
            mu: log-mean parameter
            sigma: log-standard deviation
        
        Returns:
            Probability density value
        """
        if t <= t0:
            return 0.0
        
        x = (math.log(t - t0) - mu) / sigma
        return (1 / (sigma * math.sqrt(2 * math.pi * (t - t0)))) * math.exp(-0.5 * x * x)
    
    @staticmethod
    def generate_trajectory(
        start: Point,
        end: Point,
        duration: float = 1.0,
        num_points: int = 50,
        num_impulses: int = 3
    ) -> list[Point]:
        """
        Generate realistic cursor trajectory using sigma log-normal model.
        
        Args:
            start: Starting point
            end: Ending point
            duration: Time to move cursor (seconds)
            num_points: Number of points to generate
            num_impulses: Number of overlapping velocity impulses
        
        Returns:
            List of points along trajectory
        """
        
        trajectory = []
        dt = duration / num_points
        distance = start.distance_to(end)
        
        # Normalize direction
        dx = (end.x - start.x) / distance if distance > 0 else 0
        dy = (end.y - start.y) / distance if distance > 0 else 0
        
        # Generate velocity impulses with varying parameters
        impulses = []
        for i in range(num_impulses):
            impulses.append({
                'amplitude': random.uniform(0.3, 0.8),
                'start_time': random.uniform(0, duration * 0.7),
                'mu': random.uniform(0.1, 0.5),
                'sigma': random.uniform(0.1, 0.3),
            })
        
        # Generate trajectory points
        cumulative_distance = 0
        
        for step in range(num_points + 1):
            t = step * dt
            
            # Compute velocity from superposition of log-normal impulses
            velocity = sum(
                impulse['amplitude'] * SigmaLogNormalModel.log_normal(
                    t,
                    impulse['start_time'],
                    impulse['mu'],
                    impulse['sigma']
                )
                for impulse in impulses
            )
            
            # Normalize velocity
            velocity = velocity / max(sum(i['amplitude'] for i in impulses), 0.1)
            
            # Move along trajectory
            step_distance = velocity * distance * dt
            cumulative_distance += step_distance
            
            # Ensure we don't overshoot
            if cumulative_distance >= distance:
                trajectory.append(end)
                break
            
            # Compute current position
            current_x = start.x + dx * cumulative_distance
            current_y = start.y + dy * cumulative_distance
            
            # Add micro-tremor (natural hand shaking)
            current_x += random.gauss(0, 0.5)
            current_y += random.gauss(0, 0.5)
            
            trajectory.append(Point(current_x, current_y))
        
        # Ensure endpoint is included
        if not trajectory or trajectory[-1].distance_to(end) > 1.0:
            trajectory.append(end)
        
        return trajectory


class FittsLawCalculator:
    """
    Fitts' Law: MT = a + b × log₂(2D / W)
    
    Where:
    - MT = Movement Time
    - D = Distance to target
    - W = Target width
    - a, b = empirical constants (typically a≈0.1, b≈0.1 for mouse)
    """
    
    # Empirical constants (vary by user/device)
    A = 0.1  # Intercept
    B = 0.1  # Slope
    
    @staticmethod
    def calculate_movement_time(distance: float, target_width: float) -> float:
        """
        Calculate expected human movement time using Fitts' Law.
        
        Args:
            distance: Distance to target (pixels)
            target_width: Width of target (pixels)
        
        Returns:
            Expected movement time in seconds
        """
        
        if distance == 0 or target_width == 0:
            return 0.1
        
        # Index of Difficulty
        id_bits = math.log2(2 * distance / target_width) if distance > 0 else 0
        
        # Movement time in seconds
        mt = FittsLawCalculator.A + FittsLawCalculator.B * id_bits
        
        # Add realistic variance
        variance = random.gauss(0, mt * 0.15)  # ±15% variance
        
        return max(0.1, mt + variance)


class Layer5BehavioralBiometrics:
    """
    Simulate human behavioral patterns to defeat behavioral analysis.
    """
    
    def __init__(self):
        self.logger = None
    
    async def move_mouse_human_like(
        self,
        page: pw.Page,
        target_x: float,
        target_y: float,
        duration: float | None = None
    ) -> None:
        """
        Move mouse to target using sigma log-normal trajectory.
        
        Args:
            page: Playwright page object
            target_x: Target X coordinate
            target_y: Target Y coordinate
            duration: Time to move (auto-calculated from Fitts' Law if not specified)
        """
        
        # Get current mouse position
        current_pos = await page.evaluate("() => [window.pageXOffset, window.pageYOffset]")
        current_x, current_y = current_pos[0], current_pos[1]
        
        start = Point(current_x, current_y)
        end = Point(target_x, target_y)
        distance = start.distance_to(end)
        
        # If duration not specified, use Fitts' Law
        if duration is None:
            target_width = 20  # Assume ~20px target
            duration = FittsLawCalculator.calculate_movement_time(distance, target_width)
        
        # Generate realistic trajectory
        trajectory = SigmaLogNormalModel.generate_trajectory(
            start, end,
            duration=duration,
            num_points=int(duration * 100)  # ~100 points per second
        )
        
        # Move mouse along trajectory
        for point in trajectory:
            await page.mouse.move(point.x, point.y)
            await asyncio.sleep(0.01)  # 10ms between moves
    
    async def click_human_like(
        self,
        page: pw.Page,
        x: float,
        y: float,
        button: str = "left",
        dwell_time_ms: float = 50
    ) -> None:
        """
        Click with human-like behavior:
        - Move to position with natural trajectory
        - Brief hover with micro-jitter
        - Natural click timing
        
        Args:
            page: Playwright page object
            x: Click X coordinate
            y: Click Y coordinate
            button: Mouse button (left, right, middle)
            dwell_time_ms: Time to hover before clicking (ms)
        """
        
        # Move to position with natural trajectory
        await self.move_mouse_human_like(page, x, y)
        
        # Add micro-jitter during dwell
        jitter_x = x + random.gauss(0, 2)
        jitter_y = y + random.gauss(0, 2)
        await page.mouse.move(jitter_x, jitter_y)
        
        # Brief hover
        dwell_seconds = (dwell_time_ms + random.gauss(0, dwell_time_ms * 0.3)) / 1000
        await asyncio.sleep(dwell_seconds)
        
        # Click
        await page.mouse.click(x, y, button=button)
    
    async def type_human_like(
        self,
        page: pw.Page,
        text: str,
        error_rate: float = 0.05
    ) -> None:
        """
        Type text with human-like patterns:
        - Variable inter-keystroke timing (IKT)
        - ~5% natural error rate
        - Natural corrections with backspace
        
        Args:
            page: Playwright page object
            text: Text to type
            error_rate: Probability of typing error (0.0-1.0)
        """
        
        # Bigram-based IKT (inter-keystroke timing in milliseconds)
        # Common bigrams are faster, uncommon ones slower
        bigram_times = self._get_bigram_timing_distribution()
        
        for i, char in enumerate(text):
            # Get IKT for this bigram
            if i > 0:
                bigram = text[i-1:i+1]
                ikt = bigram_times.get(bigram, random.gauss(100, 30))
                await asyncio.sleep(max(30, ikt) / 1000)  # Min 30ms
            
            # Random error with natural correction
            if random.random() < error_rate:
                await page.keyboard.press('Backspace')
                await asyncio.sleep(random.gauss(100, 30) / 1000)
                await page.keyboard.type(char)
            else:
                await page.keyboard.type(char)
    
    async def scroll_human_like(
        self,
        page: pw.Page,
        distance_px: float = 300,
        duration_seconds: float = 2.0
    ) -> None:
        """
        Scroll with momentum-based deceleration.
        
        Args:
            page: Playwright page object
            distance_px: Distance to scroll (pixels)
            duration_seconds: Duration of scroll animation
        """
        
        # Momentum-based scroll: accelerate then decelerate
        num_steps = int(duration_seconds * 60)  # 60 FPS
        
        for step in range(num_steps):
            # Ease-out cubic (deceleration)
            progress = step / max(1, num_steps - 1)
            eased = 1 - (1 - progress) ** 3
            
            current_distance = eased * distance_px
            
            # Add micro-pause at content boundaries (realistic)
            if step % 15 == 0 and random.random() < 0.1:
                await asyncio.sleep(random.gauss(200, 50) / 1000)
            
            await page.evaluate(f"window.scrollBy(0, {current_distance / num_steps})")
            await asyncio.sleep(1 / 60)  # ~16ms per frame (60 FPS)
    
    async def wait_and_read_like_human(
        self,
        page: pw.Page,
        estimated_words: int = 500,
        wpm: float = 250.0
    ) -> None:
        """
        Simulate reading time based on content.
        
        Args:
            page: Playwright page object
            estimated_words: Estimated word count of page content
            wpm: Reading speed (words per minute), ~250 is average
        """
        
        # Calculate reading time
        reading_time = (estimated_words / wpm) * 60  # seconds
        
        # Add variance (±30%)
        variance = random.gauss(0, reading_time * 0.3)
        total_time = max(1.0, reading_time + variance)
        
        # Simulate reading with micro-interactions
        start_time = time.time()
        while time.time() - start_time < total_time:
            # Random scroll
            if random.random() < 0.1:
                await self.scroll_human_like(page, random.uniform(50, 200), 0.5)
            
            # Random pause
            await asyncio.sleep(random.gauss(2, 1))
    
    @staticmethod
    def _get_bigram_timing_distribution() -> dict[str, float]:
        """Get inter-keystroke timing for common bigrams (milliseconds)."""
        
        return {
            'th': random.gauss(65, 10),
            'he': random.gauss(75, 10),
            'in': random.gauss(70, 10),
            'er': random.gauss(85, 10),
            'an': random.gauss(80, 10),
            'ed': random.gauss(90, 10),
            'it': random.gauss(75, 10),
            'or': random.gauss(85, 10),
            'en': random.gauss(80, 10),
            'ar': random.gauss(90, 10),
        }


def create_behavioral_layer() -> Layer5BehavioralBiometrics:
    """Create behavioral biometrics layer."""
    return Layer5BehavioralBiometrics()
