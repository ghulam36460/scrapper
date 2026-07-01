"""
Centralized concurrency / resource configuration.

Auto-detects the host machine's logical CPU count (physical cores x SMT /
hyper-threading) and derives sane, aggressive-but-stable pool sizes used across
every scraper. Values can be overridden with environment variables so the same
build runs well on a 2-core VM and a 16-thread laptop.

Environment overrides:
    SCRAPER_CPU_COUNT          force the detected logical CPU count
    SCRAPER_MAPS_PAGE_WORKERS  concurrent Playwright tabs for Maps extraction
    SCRAPER_IO_WORKERS         concurrent threads for HTTP/website enrichment
    SCRAPER_CPU_WORKERS        threads for CPU-bound parsing
    SCRAPER_ENRICH_WORKERS     threads for post-merge email/whatsapp backfill
"""

from __future__ import annotations

import os


def _detect_cpus() -> int:
    forced = os.getenv("SCRAPER_CPU_COUNT")
    if forced:
        try:
            return max(1, int(forced))
        except ValueError:
            pass
    # os.cpu_count() already counts hyper-threaded logical processors.
    return max(1, os.cpu_count() or 4)


CPU_COUNT: int = _detect_cpus()


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


# ----------------------------------------------------------------------------
# Pool sizing heuristics
# ----------------------------------------------------------------------------
def _detect_total_ram_gb() -> float:
    # 1) psutil = accurate + cross-platform (Windows/macOS/Linux)
    try:
        import psutil  # type: ignore
        return psutil.virtual_memory().total / (1024 ** 3)
    except Exception:
        pass
    # 2) POSIX fallback (Linux/macOS)
    try:
        import os as _os
        pages = _os.sysconf("SC_PHYS_PAGES")
        page_size = _os.sysconf("SC_PAGE_SIZE")
        return (pages * page_size) / (1024 ** 3)
    except Exception:
        pass
    # 3) conservative default
    return 8.0


TOTAL_RAM_GB: float = _detect_total_ram_gb()

# Each parallel Maps worker runs its OWN Chromium (sync Playwright is not
# thread-safe across threads). A Chromium context costs ~0.3-0.5 GB, so size
# the browser pool by BOTH cpu count and available RAM, leaving ~2 GB headroom.
_ram_browser_budget = max(1, int((TOTAL_RAM_GB - 2.0) / 0.55))
MAPS_PAGE_WORKERS: int = _env_int(
    "SCRAPER_MAPS_PAGE_WORKERS",
    max(2, min(CPU_COUNT, _ram_browser_budget, 10)),
)

# HTTP/website enrichment is almost entirely I/O-bound -> heavily oversubscribe.
IO_WORKERS: int = _env_int(
    "SCRAPER_IO_WORKERS",
    min(64, max(8, CPU_COUNT * 6)),
)

# CPU-bound HTML parsing -> match logical CPUs (selectolax/lxml release the GIL).
CPU_WORKERS: int = _env_int(
    "SCRAPER_CPU_WORKERS",
    max(2, CPU_COUNT),
)

# Post-merge contact backfill (I/O bound HTTP crawls).
ENRICH_WORKERS: int = _env_int(
    "SCRAPER_ENRICH_WORKERS",
    min(48, max(6, CPU_COUNT * 4)),
)


def summary() -> str:
    return (
        f"cpus={CPU_COUNT} ram={TOTAL_RAM_GB:.1f}GB "
        f"maps_browsers={MAPS_PAGE_WORKERS} io={IO_WORKERS} "
        f"cpu={CPU_WORKERS} enrich={ENRICH_WORKERS}"
    )


# ----------------------------------------------------------------------------
# Chromium launch tuning (hardware acceleration + speed)
# ----------------------------------------------------------------------------
# Use the integrated GPU (Intel iGPU / any non-discrete adapter) for compositing
# and rasterization. We deliberately avoid forcing software rendering. On Linux
# the ANGLE GL backend lets Chromium drive the integrated GPU; combined with
# zero-copy + GPU rasterization this offloads page rendering from the CPU so the
# CPU is free to parse HTML across the worker pool.
#
# Override with SCRAPER_DISABLE_GPU=1 to fall back to software rendering on hosts
# where the iGPU driver is unstable inside the headless sandbox.

def _gpu_enabled() -> bool:
    return os.getenv("SCRAPER_DISABLE_GPU", "0").strip() not in ("1", "true", "True")


def chromium_launch_args(headless: bool = True) -> list:
    """Return optimized Chromium CLI flags shared by every scraper."""
    args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-translate",
        "--disable-default-apps",
        "--no-first-run",
        "--no-default-browser-check",
        "--metrics-recording-only",
        "--mute-audio",
        "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows",
        "--disable-background-timer-throttling",
    ]
    if _gpu_enabled():
        # Hardware-accelerate on the integrated GPU.
        args += [
            "--ignore-gpu-blocklist",
            "--enable-gpu-rasterization",
            "--enable-zero-copy",
            "--use-gl=angle",
            "--use-angle=gl",
            "--enable-accelerated-2d-canvas",
        ]
    else:
        args += ["--disable-gpu"]
    return args


def launch_kwargs(headless: bool = True) -> dict:
    """Convenience kwargs for chromium.launch(...)."""
    return {"headless": headless, "args": chromium_launch_args(headless)}
