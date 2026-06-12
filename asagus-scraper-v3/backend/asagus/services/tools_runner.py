"""
Tools Runner — Launch and manage Download folder tools from the API.

Each tool in the Download/ directory can be started as a subprocess,
using the same Python environment as the backend. Tools share the same
venv/dependencies so no isolation penalty.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

# Root of the Download folder — resolved and verified
_DOWNLOAD_ROOT = Path(__file__).resolve().parents[4] / "Download"
_ASAGUS_LAUNCHER = _DOWNLOAD_ROOT / "asagus_tool_launcher.py"
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_VENV_PYTHON = _BACKEND_ROOT / ".venv" / "bin" / "python"
_BACKEND_PYTHON = _BACKEND_VENV_PYTHON if _BACKEND_VENV_PYTHON.exists() else Path(sys.executable).resolve()
_PIPELINE_CONFIG = _DOWNLOAD_ROOT / "asagus_pipeline.json"
_RUNS_ROOT = _DOWNLOAD_ROOT / ".asagus-runs"

# ─── Security: Arg sanitization ──────────────────────────────────────────────
_SHELL_METACHARS = frozenset(";&|$`\\\n\r\t")
_MAX_ARG_COUNT = 20
_MAX_ARG_LENGTH = 512
_MAX_MODE_TOOL_IDS = (
    "agent-reach",
    "scrapegraph-ai",
    "scrapling",
    "firecrawl",
    "maxun",
    "outreach",
    "outreach-system",
    "outreach-scraper",
    "maps-scraper",
    "scrapy",
    "whatsapp-detector",
)


def _sanitize_tool_args(args: list[str]) -> list[str]:
    """Validate and sanitize subprocess arguments to prevent injection."""
    if len(args) > _MAX_ARG_COUNT:
        raise ValueError(f"Too many arguments (max {_MAX_ARG_COUNT})")
    sanitized: list[str] = []
    for arg in args:
        if not isinstance(arg, str):
            raise ValueError(f"Argument must be a string, got {type(arg).__name__}")
        if len(arg) > _MAX_ARG_LENGTH:
            raise ValueError(f"Argument too long (max {_MAX_ARG_LENGTH} chars)")
        if any(c in arg for c in _SHELL_METACHARS):
            raise ValueError(f"Argument contains forbidden characters: {arg!r}")
        # Prevent path traversal in args
        if ".." in arg:
            raise ValueError(f"Path traversal not allowed in arguments: {arg!r}")
        sanitized.append(arg)
    return sanitized


# ─── Tool Metadata Registry ──────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "agent-reach": {
        "name": "Agent Reach",
        "description": "AI-powered outreach agent for lead generation and contact automation",
        "folder": "Agent-Reach-main",
        "entry_points": ["asagus:auto", "main.py", "app.py", "run.py", "agent_reach.py"],
        "category": "outreach",
        "tags": ["outreach", "AI", "agent"],
    },
    "scrapegraph-ai": {
        "name": "ScrapeGraph AI",
        "description": "AI-powered web scraper using LLMs for intelligent data extraction",
        "folder": "Scrapegraph-ai-main",
        "entry_points": ["asagus:auto", "main.py", "demo.py", "examples/"],
        "category": "scraping",
        "tags": ["AI", "LLM", "extraction"],
    },
    "scrapling": {
        "name": "Scrapling",
        "description": "Adaptive web scraping library with automatic selector healing",
        "folder": "Scrapling-main",
        "entry_points": ["asagus:auto", "main.py", "demo.py", "scrapling/"],
        "category": "scraping",
        "tags": ["adaptive", "stealth", "playwright"],
    },
    "firecrawl": {
        "name": "Firecrawl",
        "description": "Turn websites into LLM-ready data with crawling and scraping API",
        "folder": "firecrawl-main",
        "entry_points": ["asagus:auto", "apps/api/src/index.ts", "main.py", "run.py"],
        "category": "scraping",
        "tags": ["crawl", "LLM", "API"],
    },
    "maxun": {
        "name": "Maxun",
        "description": "No-code visual web data extraction platform",
        "folder": "maxun-develop",
        "entry_points": ["asagus:auto", "server/src/index.ts", "main.py", "app.py"],
        "category": "scraping",
        "tags": ["no-code", "visual", "extraction"],
    },
    "outreach": {
        "name": "Outreach Tool",
        "description": "Automated outreach system for scraped leads",
        "folder": "outreach-main",
        "entry_points": ["asagus:auto", "main.py", "outreach.py", "app.py", "start.sh"],
        "category": "outreach",
        "tags": ["outreach", "automation", "email"],
    },
    "outreach-system": {
        "name": "Outreach System",
        "description": "Full outreach automation system with CRM integration",
        "folder": "outreach-system-main",
        "entry_points": ["asagus:auto", "main.py", "app.py", "system.py"],
        "category": "outreach",
        "tags": ["CRM", "automation", "sequences"],
    },
    "outreach-scraper": {
        "name": "Outreach Scraper",
        "description": "Specialized scraper targeting contact info for outreach campaigns",
        "folder": "scrapping-for-outreach-tool-main",
        "entry_points": ["asagus:auto", "backend/enhanced_scraper.py", "backend/app.py", "main.py", "scraper.py", "run.py"],
        "category": "scraping",
        "tags": ["contact", "email", "phone"],
    },
    "maps-scraper": {
        "name": "Google Maps Scraper",
        "description": "High-performance Google Maps business data extractor",
        "folder": "scrapping-tool-of-maps-main",
        "entry_points": ["asagus:auto", "backend/enhanced_scraper.py", "backend/app.py", "main.py", "maps_scraper.py", "run.py"],
        "category": "scraping",
        "tags": ["maps", "business", "location"],
    },
    "scrapy": {
        "name": "Scrapy Spider",
        "description": "Industrial-scale web crawling with Scrapy framework",
        "folder": "scrapy-master",
        "entry_points": ["asagus:auto", "scrapy.cfg", "main.py"],
        "category": "scraping",
        "tags": ["scrapy", "spider", "crawl"],
    },
    "whatsapp-detector": {
        "name": "WhatsApp Number Detector",
        "description": "Detect and validate WhatsApp numbers from scraped contacts",
        "folder": "whatsapp-number-detector-main",
        "entry_points": ["asagus:auto", "server/index.js", "main.py", "detector.py", "whatsapp_check.py"],
        "category": "enrichment",
        "tags": ["whatsapp", "phone", "validation"],
    },
}

# In-memory registry of running tool processes
_running_tools: dict[str, dict[str, Any]] = {}


def max_mode_tool_ids() -> list[str]:
    """Return Download tools that should be launched with ASAGUS max mode."""
    available = {tool["id"] for tool in list_tools() if tool["available"]}
    return [tool_id for tool_id in _MAX_MODE_TOOL_IDS if tool_id in available]


def list_tools() -> list[dict[str, Any]]:
    """Return all registered tools with availability status."""
    result = []
    for tool_id, meta in TOOL_REGISTRY.items():
        folder = _DOWNLOAD_ROOT / meta["folder"]
        available = folder.exists()

        # Find the actual entry point
        entry_point = None
        if available:
            entry_point = _find_entry_point(folder, meta)

        result.append({
            "id": tool_id,
            "name": meta["name"],
            "description": meta["description"],
            "category": meta["category"],
            "tags": meta["tags"],
            "folder": meta["folder"],
            "available": available,
            "entry_point": entry_point,
            "folder_path": str(folder) if available else None,
        })
    return result


def get_tool(tool_id: str) -> dict[str, Any] | None:
    """Get tool metadata by ID."""
    meta = TOOL_REGISTRY.get(tool_id)
    if not meta:
        return None
    folder = _DOWNLOAD_ROOT / meta["folder"]
    entry_point = None
    if folder.exists():
        entry_point = _find_entry_point(folder, meta)
    return {
        "id": tool_id,
        **meta,
        "available": folder.exists(),
        "entry_point": entry_point,
        "folder_path": str(folder),
    }


async def run_tool(
    tool_id: str,
    args: list[str] | None = None,
    env_extra: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Start a tool as a subprocess. Returns a run_id for status polling.
    The tool inherits the backend's Python environment.
    """
    meta = TOOL_REGISTRY.get(tool_id)
    if not meta:
        raise ValueError(f"Unknown tool: {tool_id}")

    folder = _DOWNLOAD_ROOT / meta["folder"]
    if not folder.exists():
        raise FileNotFoundError(f"Tool folder not found: {folder}")

    # Path traversal guard: ensure resolved folder is inside Download root
    resolved_folder = folder.resolve()
    if not resolved_folder.is_relative_to(_DOWNLOAD_ROOT.resolve()):
        raise ValueError(f"Tool folder escapes Download root: {resolved_folder}")

    # Find entry point
    entry_point = _find_entry_point(folder, meta)

    if not entry_point:
        raise FileNotFoundError(f"No runnable entry point found for {tool_id}")

    run_id = str(uuid.uuid4())
    cmd: list[str]

    if entry_point == "asagus:auto":
        cmd = [str(_BACKEND_PYTHON), str(_ASAGUS_LAUNCHER), "--tool-id", tool_id]
    elif entry_point.endswith(".py"):
        cmd = [str(_BACKEND_PYTHON), str(folder / entry_point)]
    elif entry_point.endswith(".ts"):
        node_path = shutil.which("node") or "node"
        ts_node = shutil.which("ts-node") or shutil.which("npx")
        if ts_node:
            cmd = [ts_node, "ts-node", str(folder / entry_point)] if "npx" in (ts_node or "") else [ts_node, str(folder / entry_point)]
        else:
            cmd = [node_path, str(folder / entry_point)]
    else:
        cmd = [str(_BACKEND_PYTHON), str(folder / entry_point)]

    if args:
        sanitized_args = _sanitize_tool_args(args)
        cmd.extend(sanitized_args)

    env = {
        **os.environ,
        "ASAGUS_TOOL_ID": tool_id,
        "ASAGUS_BACKEND_ROOT": str(_BACKEND_ROOT),
        "ASAGUS_BACKEND_PYTHON": str(_BACKEND_PYTHON),
        "ASAGUS_DOWNLOAD_ROOT": str(_DOWNLOAD_ROOT),
        "ASAGUS_PIPELINE_CONFIG": str(_PIPELINE_CONFIG),
        "ASAGUS_RUNS_ROOT": str(_RUNS_ROOT),
        **(env_extra or {}),
    }

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(folder),
            env=env,
        )

        _running_tools[run_id] = {
            "run_id": run_id,
            "tool_id": tool_id,
            "tool_name": meta["name"],
            "command": cmd,
            "pid": process.pid,
            "status": "running",
            "started_at": time.time(),
            "stdout": [],
            "stderr": [],
            "exit_code": None,
            "process": process,
        }

        # Start async reader tasks
        asyncio.create_task(_read_output(run_id, process))

        return {
            "run_id": run_id,
            "tool_id": tool_id,
            "tool_name": meta["name"],
            "pid": process.pid,
            "status": "running",
            "command": " ".join(str(c) for c in cmd),
        }

    except Exception as exc:
        raise RuntimeError(f"Failed to start {tool_id}: {exc}") from exc


def _find_entry_point(folder: Path, meta: dict[str, Any]) -> str | None:
    for ep in meta.get("entry_points", []):
        if ep == "asagus:auto":
            if _ASAGUS_LAUNCHER.exists():
                return ep
            continue
        candidate = folder / ep
        if candidate.exists() and candidate.is_file():
            return ep
    return None


async def launch_max_mode_tools(
    *,
    job_id: str,
    query: str,
    location: str,
    limit: int,
    website_filter: str,
    network_enabled: bool,
    tool_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Launch available Download tools for a max-mode scrape."""
    selected = tool_ids or max_mode_tool_ids()
    results: list[dict[str, Any]] = []
    run_dir = _RUNS_ROOT / job_id
    run_dir.mkdir(parents=True, exist_ok=True)
    pipeline_manifest = run_dir / "pipeline.json"
    pipeline_payload = {
        "job_id": job_id,
        "mode": "max",
        "query": query,
        "location": location,
        "limit": limit,
        "website_filter": website_filter,
        "network_enabled": network_enabled,
        "backend_root": str(_BACKEND_ROOT),
        "backend_python": str(_BACKEND_PYTHON),
        "download_root": str(_DOWNLOAD_ROOT),
        "pipeline_config": str(_PIPELINE_CONFIG),
        "runs_root": str(_RUNS_ROOT),
        "selected_tools": selected,
        "challenge_policy": (
            "Detect and report CAPTCHA, 403, 429, robots, and access-control pages "
            "for manual review; do not force bypass."
        ),
        "created_at": time.time(),
    }
    pipeline_manifest.write_text(json.dumps(pipeline_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    env = {
        "ASAGUS_JOB_ID": job_id,
        "ASAGUS_QUERY": query,
        "ASAGUS_LOCATION": location,
        "ASAGUS_LIMIT": str(limit),
        "ASAGUS_MODE": "max",
        "ASAGUS_WEBSITE_FILTER": website_filter,
        "ASAGUS_DRY_RUN": "1",
        "ASAGUS_TOOL_REAL_RUN": "1" if network_enabled else "0",
        "ASAGUS_TOOL_MAX_RESULTS": str(min(max(limit, 5), 25)),
        "ASAGUS_TOOL_TIMEOUT_SECONDS": "240",
        "ASAGUS_BACKEND_ROOT": str(_BACKEND_ROOT),
        "ASAGUS_BACKEND_PYTHON": str(_BACKEND_PYTHON),
        "ASAGUS_DOWNLOAD_ROOT": str(_DOWNLOAD_ROOT),
        "ASAGUS_PIPELINE_CONFIG": str(_PIPELINE_CONFIG),
        "ASAGUS_PIPELINE_MANIFEST": str(pipeline_manifest),
        "ASAGUS_RUNS_ROOT": str(_RUNS_ROOT),
    }
    args = ["--mode", "max", "--query", query, "--location", location, "--limit", str(min(max(limit, 5), 25))]
    for tool_id in selected:
        try:
            result = await run_tool(tool_id, args=args, env_extra=env)
        except Exception as exc:
            result = {
                "tool_id": tool_id,
                "status": "failed_to_start",
                "error": str(exc),
            }
        results.append(result)
    return results


async def _read_output(run_id: str, process: asyncio.subprocess.Process) -> None:
    """Async task: read stdout/stderr and buffer last 200 lines each. Auto-kill after 30 min."""
    run = _running_tools.get(run_id)
    if not run:
        return

    _MAX_TOOL_RUNTIME_SECONDS = 1800  # 30 minutes

    async def read_stream(stream: asyncio.StreamReader | None, key: str) -> None:
        if stream is None:
            return
        while True:
            try:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                buf: list[str] = run[key]
                buf.append(text)
                if len(buf) > 200:
                    buf.pop(0)
            except Exception:
                break

    try:
        await asyncio.wait_for(
            asyncio.gather(
                read_stream(process.stdout, "stdout"),
                read_stream(process.stderr, "stderr"),
            ),
            timeout=_MAX_TOOL_RUNTIME_SECONDS,
        )
    except asyncio.TimeoutError:
        # Kill the process if it exceeds the timeout
        try:
            process.kill()
        except Exception:
            pass
        if run_id in _running_tools:
            _running_tools[run_id]["status"] = "killed_timeout"
            _running_tools[run_id]["exit_code"] = -9
            _running_tools[run_id].pop("process", None)
        return

    exit_code = await process.wait()
    if run_id in _running_tools:
        _running_tools[run_id]["exit_code"] = exit_code
        _running_tools[run_id]["status"] = "completed" if exit_code == 0 else "failed"
        _running_tools[run_id].pop("process", None)


def get_tool_status(run_id: str) -> dict[str, Any] | None:
    """Return current status and buffered output for a run."""
    run = _running_tools.get(run_id)
    if not run:
        return None
    return {
        "run_id": run["run_id"],
        "tool_id": run["tool_id"],
        "tool_name": run["tool_name"],
        "pid": run["pid"],
        "status": run["status"],
        "started_at": run["started_at"],
        "exit_code": run["exit_code"],
        "stdout": run["stdout"][-100:],
        "stderr": run["stderr"][-100:],
    }


def kill_tool(run_id: str) -> bool:
    """Kill a running tool process."""
    run = _running_tools.get(run_id)
    if not run:
        return False
    process = run.get("process")
    if process:
        try:
            process.kill()
        except Exception:
            pass
    run["status"] = "killed"
    run.pop("process", None)
    return True


def list_running_tools() -> list[dict[str, Any]]:
    """List all active/recent tool runs."""
    result = []
    for run_id, run in _running_tools.items():
        result.append({
            "run_id": run_id,
            "tool_id": run["tool_id"],
            "tool_name": run["tool_name"],
            "status": run["status"],
            "started_at": run["started_at"],
            "exit_code": run["exit_code"],
        })
    return sorted(result, key=lambda x: x["started_at"], reverse=True)
