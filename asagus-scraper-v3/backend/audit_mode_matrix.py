"""Run an offline ASAGUS job matrix across modes and discovery submodes."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request


BASE_URL = "http://127.0.0.1:8000"
MODES = ["fast", "balanced", "focused", "adaptive", "deep", "deep_agent", "parallel", "comprehensive", "research"]
DISCOVERY_MODES = ["website_first", "social_first", "social_only"]
TERMINAL = {"completed", "failed", "cancelled"}
HTTP_TIMEOUT_SECONDS = 120


def request_json(path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if payload is not None else {},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def run_case(mode: str, discovery_mode: str) -> dict[str, object]:
    payload = {
        "query": "restaurants",
        "location": "Lahore",
        "limit": 5,
        "max_pages": 5,
        "mode": mode,
        "discovery_mode": discovery_mode,
        "enable_network_fetch": False,
        "enable_search_discovery": False,
        "llm_enabled": False,
        "archive_raw_html": False,
        "respect_robots_txt": True,
        "skip_existing": False,
    }
    job = request_json("/api/jobs", payload)
    job_id = str(job["id"])
    for _ in range(90):
        time.sleep(1)
        detail = request_json(f"/api/jobs/{job_id}")
        current = detail["job"]
        if isinstance(current, dict) and str(current["status"]) in TERMINAL:
            return current
    raise TimeoutError(f"{mode}/{discovery_mode} did not finish in 90 seconds")


def main() -> int:
    failures: list[dict[str, object]] = []
    print("ASAGUS offline mode matrix: limit=5, max_pages=5", flush=True)
    print(f"API: {BASE_URL}", flush=True)
    for mode in MODES:
        for discovery_mode in DISCOVERY_MODES:
            label = f"{mode:10} / {discovery_mode:13}"
            try:
                job = run_case(mode, discovery_mode)
                status = str(job["status"])
                print(
                    f"{label} -> {status:10} "
                    f"processed={job.get('processed_targets')} "
                    f"skipped={job.get('skipped_targets')} "
                    f"records={job.get('records_found')} "
                    f"error={str(job.get('error') or '')[:80]}",
                    flush=True,
                )
                if status != "completed":
                    failures.append(job)
            except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as exc:
                print(f"{label} -> ERROR      {exc}", flush=True)
                failures.append({"mode": mode, "discovery_mode": discovery_mode, "error": str(exc)})
    print(f"\nSummary: {len(MODES) * len(DISCOVERY_MODES) - len(failures)} passed, {len(failures)} failed", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
