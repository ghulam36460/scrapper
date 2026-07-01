"""
ASAGUS Adapter for the Google Maps scraping tool (scrapping-tool-of-maps-main).

This tool has NO pip package — it is integrated by importing its own backend
modules directly. It is fully mode-aware: the ASAGUS main scraper mode selects
which internal engine runs, mirroring the tool's own depth tiers:

    fast / focused / balanced        -> enhanced_scraper.EnhancedGoogleMapsScraper
    deep / research / comprehensive  -> deep_scraper.DeepMapsScraper
    deep_agent / adaptive / parallel -> ultra_scraper.UltraScraper
    max                              -> maximum_scraper.MaximumScraper

It runs as an autonomous worker: given a query + location it scrapes business
data and writes a unified CSV (<tool_id>.csv) that the ASAGUS backend's
csv_merger ingests back into the main pipeline. Designed to run in parallel
with the other Download scraper workers.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from threading import Event
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _THIS_DIR / "backend"
sys.path.insert(0, str(_THIS_DIR.parent))  # for unified_tool_adapter
sys.path.insert(0, str(_BACKEND_DIR))      # for the tool's own backend modules

from unified_tool_adapter import UnifiedToolAdapter  # noqa: E402


# Map ASAGUS main-scraper modes to this tool's internal depth engines.
# Each value is (engine_module, engine_class, extra_kwargs).
_MODE_ENGINE_MAP: dict[str, tuple[str, str]] = {
    "fast": ("enhanced_scraper", "EnhancedGoogleMapsScraper"),
    "focused": ("enhanced_scraper", "EnhancedGoogleMapsScraper"),
    "balanced": ("enhanced_scraper", "EnhancedGoogleMapsScraper"),
    "deep": ("deep_scraper", "DeepBusinessScraper"),
    "research": ("deep_scraper", "DeepBusinessScraper"),
    "comprehensive": ("deep_scraper", "DeepBusinessScraper"),
    "deep_agent": ("ultra_scraper", "UltraDeepScraper"),
    "adaptive": ("ultra_scraper", "UltraDeepScraper"),
    "parallel": ("ultra_scraper", "UltraDeepScraper"),
    "max": ("maximum_scraper", "MaximumScraper"),
}

# Fallback chain: if the selected engine fails to import, degrade gracefully.
_FALLBACK_ENGINES: list[tuple[str, str]] = [
    ("enhanced_scraper", "EnhancedGoogleMapsScraper"),
    ("enhanced_scraper_sync", "GoogleMapsScraper"),
    ("scraper", "GoogleMapsScraper"),
]


class MapsScraperAdapter(UnifiedToolAdapter):
    """Mode-aware autonomous worker around the Maps scraping backend."""

    def _resolve_engine(self) -> tuple[str, str]:
        return _MODE_ENGINE_MAP.get(self.mode, ("enhanced_scraper", "EnhancedGoogleMapsScraper"))

    def _website_filter_value(self) -> str:
        wf = (self.website_filter or "all").lower()
        if wf in {"no_website", "without", "no"}:
            return "without"
        if wf in {"with_website", "with", "has_website"}:
            return "with"
        return "all"

    def _build_engine(self, module_name: str, class_name: str, max_results: int):
        module = __import__(module_name)
        engine_cls = getattr(module, class_name)
        kwargs: dict[str, Any] = {
            "max_results": max_results,
            "headless": True,
            "website_filter": self._website_filter_value(),
            "logger": logging.getLogger(f"asagus.maps.{module_name}"),
        }
        # MAX/ultra/deep engines support extra depth toggles; pass them when present.
        if class_name in {"MaximumScraper", "DeepBusinessScraper"}:
            kwargs["deep_search"] = True
        if class_name in {"UltraDeepScraper", "MaximumScraper"}:
            kwargs["verify_socials"] = True
        if class_name in {"UltraDeepScraper"}:
            kwargs["parallel_engines"] = True
        # Concurrency scales with mode intensity.
        try:
            engine = engine_cls(**kwargs)
        except TypeError:
            # Some engines (enhanced) take concurrent_extractions instead.
            kwargs.pop("deep_search", None)
            kwargs.pop("verify_socials", None)
            kwargs.pop("parallel_engines", None)
            if class_name in {"EnhancedGoogleMapsScraper"}:
                kwargs["concurrent_extractions"] = 4 if self.mode == "max" else 2
            engine = engine_cls(**kwargs)
        return engine

    def _run_engine(self, max_results: int) -> tuple[list[dict[str, Any]], str]:
        """Try the mode engine, then fall back through simpler engines."""
        attempts: list[tuple[str, str]] = [self._resolve_engine(), *_FALLBACK_ENGINES]
        last_error = ""
        seen: set[tuple[str, str]] = set()
        for module_name, class_name in attempts:
            if (module_name, class_name) in seen:
                continue
            seen.add((module_name, class_name))
            try:
                engine = self._build_engine(module_name, class_name, max_results)
            except Exception as exc:  # import / construct failure -> try next
                last_error = f"{module_name}.{class_name}: {exc}"
                continue
            try:
                rows = engine.scrape(self.query, self.location, Event())
                rows = [self._to_dict(row) for row in (rows or [])]
                return rows, f"{module_name}.{class_name}"
            except Exception as exc:
                last_error = f"{module_name}.{class_name} scrape failed: {exc}"
                # CAPTCHA / access-control -> stop, surface for manual review
                if any(t in str(exc).lower() for t in ("captcha", "unusual traffic", "403", "robot")):
                    raise
                continue
        raise RuntimeError(last_error or "no maps engine available")

    @staticmethod
    def _is_useful(row: dict[str, Any]) -> bool:
        keys = ("name", "phone", "whatsapp", "email", "website", "website_url", "address")
        return any(str(row.get(k, "")).strip() for k in keys)

    @staticmethod
    def _to_dict(row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return row
        to_dict = getattr(row, "to_dict", None)
        if callable(to_dict):
            return to_dict()
        return dict(getattr(row, "__dict__", {}) or {})

    def run(self) -> dict[str, Any]:
        context = self.get_job_context()

        if not self.real_run:
            payload = {
                "tool_id": self.tool_id,
                "status": "prepared",
                "message": "Maps scraper ready; real run disabled (dry run).",
                "mode": self.mode,
                "selected_engine": ".".join(self._resolve_engine()),
                "job_context": context,
            }
            self.save_metadata_json(payload)
            return payload

        max_results = min(max(self.limit, 1), int(os.environ.get("ASAGUS_TOOL_MAX_RESULTS", "25")))
        started = time.time()
        try:
            rows, engine_used = self._run_engine(max_results)
        except Exception as exc:
            message = str(exc)
            challenge = any(t in message.lower() for t in ("captcha", "unusual traffic", "403", "robot"))
            payload = {
                "tool_id": self.tool_id,
                "status": "manual_review_required" if challenge else "failed",
                "message": message[:500],
                "challenge_or_access_control": challenge,
                "mode": self.mode,
                "job_context": context,
            }
            self.save_metadata_json(payload)
            return payload

        # Drop empty placeholder rows; keep only records with a useful field.
        rows = [r for r in rows if self._is_useful(r)]

        # Tag provenance and write the unified CSV consumed by csv_merger.
        for row in rows:
            row.setdefault("source_tool", self.tool_id)
        self.save_records_csv(rows)

        payload = {
            "tool_id": self.tool_id,
            "status": "completed",
            "mode": self.mode,
            "engine_used": engine_used,
            "records": len(rows),
            "output_csv": str(self.csv_path),
            "elapsed_seconds": round(time.time() - started, 2),
            "job_context": context,
        }
        self.save_metadata_json(payload)
        return payload


def main() -> None:
    import json

    print(json.dumps(MapsScraperAdapter().run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
