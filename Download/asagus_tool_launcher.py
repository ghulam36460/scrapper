from __future__ import annotations

import argparse
import csv
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _int_env(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)) or default)
    except ValueError:
        return default


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers: list[str] = []
    for row in rows:
        for key in row:
            if key not in headers:
                headers.append(key)
    if not headers:
        headers = ["status"]
        rows = [{"status": "empty"}]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _module_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def _run_maps_tool(tool_id: str, root: Path, query: str, location: str, limit: int, output_dir: Path) -> dict[str, Any]:
    if _env("ASAGUS_TOOL_REAL_RUN", "0") != "1":
        return {
            "status": "prepared",
            "message": "Real maps/browser run disabled for this tool launch; ASAGUS core job is the active scraper.",
        }

    backend_dir = root / "backend"
    if not backend_dir.exists():
        return {"status": "unavailable", "message": "backend folder not found"}
    sys.path.insert(0, str(backend_dir))
    max_results = min(max(limit, 1), _int_env("ASAGUS_TOOL_MAX_RESULTS", 25))
    try:
        from enhanced_scraper import EnhancedGoogleMapsScraper  # type: ignore

        scraper = EnhancedGoogleMapsScraper(
            max_results=max_results,
            headless=True,
            website_filter="without" if _env("ASAGUS_WEBSITE_FILTER") == "no_website" else "all",
            concurrent_extractions=4 if _env("ASAGUS_MODE") == "max" else 2,
        )
        rows = scraper.scrape_sync(query, location)
        csv_path = output_dir / f"{tool_id}.csv"
        _write_csv(csv_path, rows)
        return {"status": "completed", "records": len(rows), "output_csv": str(csv_path)}
    except Exception as exc:
        message = str(exc)
        challenge = any(token in message.lower() for token in ("captcha", "403", "unusual traffic", "robot"))
        return {
            "status": "manual_review_required" if challenge else "failed",
            "message": message[:500],
            "challenge_or_access_control": challenge,
        }


def _run_outreach_score(root: Path, output_dir: Path) -> dict[str, Any]:
    sys.path.insert(0, str(root))
    try:
        from lead_scorer import score_and_segment_lead  # type: ignore

        sample = {
            "business": _env("ASAGUS_QUERY", "business"),
            "category": _env("ASAGUS_QUERY", ""),
            "city": _env("ASAGUS_LOCATION", ""),
            "website_exists": _env("ASAGUS_WEBSITE_FILTER") != "no_website",
            "reviews_count": 0,
            "social_presence": "unknown",
        }
        scored = score_and_segment_lead(sample)
        _write_json(output_dir / "outreach-system-score.json", scored)
        return {"status": "completed", "lead_score": scored.get("lead_score"), "segment": scored.get("segment")}
    except Exception as exc:
        return {"status": "failed", "message": str(exc)[:500]}


def main() -> int:
    parser = argparse.ArgumentParser(description="ASAGUS Download tool launcher")
    parser.add_argument("--tool-id", default=_env("ASAGUS_TOOL_ID"))
    parser.add_argument("--mode", default=_env("ASAGUS_MODE", "balanced"))
    parser.add_argument("--query", default=_env("ASAGUS_QUERY"))
    parser.add_argument("--location", default=_env("ASAGUS_LOCATION"))
    parser.add_argument("--limit", type=int, default=_int_env("ASAGUS_LIMIT", 25))
    args, _unknown = parser.parse_known_args()

    root = Path.cwd()
    download_root = Path(__file__).resolve().parent
    job_id = _env("ASAGUS_JOB_ID", "manual")
    runs_root = Path(_env("ASAGUS_RUNS_ROOT", str(download_root / ".asagus-runs")))
    output_dir = runs_root / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    root_pipeline = _read_json(Path(_env("ASAGUS_PIPELINE_CONFIG", str(download_root / "asagus_pipeline.json"))))
    pipeline_manifest = _read_json(Path(_env("ASAGUS_PIPELINE_MANIFEST", str(output_dir / "pipeline.json"))))
    tool_config = _read_json(root / ".asagus" / "config.json")
    timeout = _int_env("ASAGUS_TOOL_TIMEOUT_SECONDS", 240)

    def _timeout(_signum: int, _frame: Any) -> None:
        raise TimeoutError(f"ASAGUS tool timeout after {timeout}s")

    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, _timeout)
        signal.alarm(timeout)

    started = time.time()
    payload: dict[str, Any] = {
        "tool_id": args.tool_id,
        "mode": args.mode,
        "job_id": job_id,
        "query": args.query,
        "location": args.location,
        "limit": args.limit,
        "cwd": str(root),
        "started_at": started,
        "dry_run": _env("ASAGUS_DRY_RUN", "1") == "1",
        "backend_root": _env("ASAGUS_BACKEND_ROOT", str((download_root / "../asagus-scraper-v3/backend").resolve())),
        "backend_python": _env("ASAGUS_BACKEND_PYTHON", str(download_root / "../asagus-scraper-v3/backend/.venv/bin/python")),
        "python_executable": sys.executable,
        "python_prefix": sys.prefix,
        "pipeline_output_dir": str(output_dir),
        "root_pipeline": root_pipeline,
        "pipeline_manifest": pipeline_manifest,
        "tool_config": tool_config,
        "pipeline": {
            "upstream": ["asagus.core.discovery", "asagus.core.fetch", "asagus.core.extraction"],
            "current": args.tool_id,
            "downstream": ["asagus.core.enrichment", "asagus.core.storage", "asagus.core.indexing"],
            "contract": "job-context-json-and-csv-artifacts",
        },
    }

    try:
        if args.tool_id in {"maps-scraper", "outreach-scraper"}:
            result = _run_maps_tool(args.tool_id, root, args.query, args.location, args.limit, output_dir)
        elif args.tool_id == "outreach-system":
            result = _run_outreach_score(root, output_dir)
        elif args.tool_id == "scrapling":
            result = {"status": "completed", "package_available": _module_available("scrapling")}
        elif args.tool_id == "scrapy":
            result = {"status": "completed", "package_available": _module_available("scrapy")}
        elif args.tool_id == "agent-reach":
            result = {"status": "completed", "package_available": _module_available("agent_reach")}
        elif args.tool_id == "scrapegraph-ai":
            result = {"status": "prepared", "package_available": _module_available("scrapegraphai")}
        elif args.tool_id == "firecrawl":
            result = {"status": "prepared", "api_key_configured": bool(_env("FIRECRAWL_API_KEY"))}
        elif args.tool_id == "whatsapp-detector":
            result = {"status": "prepared", "message": "Node WhatsApp service is available; ASAGUS core enrichment generates wa.me links."}
        else:
            result = {"status": "prepared", "message": "ASAGUS context received by Download tool wrapper."}
    except TimeoutError as exc:
        result = {"status": "timeout", "message": str(exc)}
    except Exception as exc:
        result = {"status": "failed", "message": str(exc)[:500]}
    finally:
        if hasattr(signal, "alarm"):
            signal.alarm(0)

    payload.update(result)
    payload["finished_at"] = time.time()
    payload["elapsed_seconds"] = round(payload["finished_at"] - started, 3)
    output_path = output_dir / f"{args.tool_id or 'tool'}.json"
    payload["output_json"] = str(output_path)
    _write_json(output_path, payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("status") not in {"failed", "timeout"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
