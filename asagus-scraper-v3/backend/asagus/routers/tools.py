"""
Tools Router — Download folder tool management and package installer.

Security hardening:
- Package names are validated against PyPI naming conventions
- Rate limiting on installs (tracked in-memory)
- Max concurrent tool runs enforced
- All tool launches logged for audit
"""
from __future__ import annotations

import asyncio
import logging
import re
import sys
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from asagus.services import tools_runner
from asagus.routers.deps import require_operator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["tools"])

# ─── Security: Rate limiting for package installs ───────────────────────
_install_timestamps: list[float] = []
_MAX_INSTALLS_PER_MINUTE = 5
_MAX_CONCURRENT_TOOL_RUNS = 12

# PyPI package name pattern (PEP 508 compliant)
_VALID_PACKAGE_RE = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?"
    r"(\[([a-zA-Z0-9._-]+,?\s*)*\])?"  # extras like [dev,test]
    r"([<>=!~]{1,2}[a-zA-Z0-9.*]+)?$"  # version specifiers
)

# Known dangerous package names that should never be installed
_BLOCKED_PACKAGES = frozenset({
    "os", "sys", "subprocess", "shutil", "pathlib",
    "eval", "exec", "compile", "builtins", "__builtin__",
})


def _check_install_rate_limit() -> None:
    """Enforce max installs per minute."""
    now = time.time()
    # Purge entries older than 60s
    while _install_timestamps and _install_timestamps[0] < now - 60:
        _install_timestamps.pop(0)
    if len(_install_timestamps) >= _MAX_INSTALLS_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limited: max {_MAX_INSTALLS_PER_MINUTE} installs per minute",
        )
    _install_timestamps.append(now)


def _validate_package_name(package: str) -> str:
    """Validate and sanitize a package name. Returns the cleaned name."""
    package = package.strip()
    if not package:
        raise HTTPException(status_code=400, detail="Package name is required")
    if len(package) > 128:
        raise HTTPException(status_code=400, detail="Package name too long (max 128 chars)")

    # Extract base name (before version spec) for blocklist check
    base_name = re.split(r"[<>=!~\[\]]", package)[0].strip().lower()
    if base_name in _BLOCKED_PACKAGES:
        raise HTTPException(status_code=400, detail=f"Package '{base_name}' is not allowed")

    # Validate against PyPI naming pattern
    if not _VALID_PACKAGE_RE.match(package):
        raise HTTPException(
            status_code=400,
            detail="Invalid package name. Must follow PyPI naming (e.g. 'requests', 'scrapy==2.11.0')",
        )

    # Final safety check: no shell metacharacters
    if any(c in package for c in ";|&$`\\\n\r\t"):
        raise HTTPException(status_code=400, detail="Invalid characters in package name")

    return package


# ─── Download Tools ──────────────────────────────────────────────────────

@router.get("/tools")
async def list_tools() -> dict[str, Any]:
    """List all tools in the Download folder with availability status."""
    tool_list = tools_runner.list_tools()
    return {"count": len(tool_list), "tools": tool_list}


@router.get("/tools/runs")
async def list_tool_runs() -> dict[str, Any]:
    """List all active and recent tool runs."""
    runs = tools_runner.list_running_tools()
    return {"count": len(runs), "runs": runs}


@router.post("/tools/{tool_id}/run", dependencies=[Depends(require_operator)])
async def run_tool(
    tool_id: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Start a Download tool as a background subprocess."""
    # Enforce max concurrent runs
    active_runs = [r for r in tools_runner.list_running_tools() if r.get("status") == "running"]
    if len(active_runs) >= _MAX_CONCURRENT_TOOL_RUNS:
        raise HTTPException(
            status_code=429,
            detail=f"Max {_MAX_CONCURRENT_TOOL_RUNS} concurrent tool runs allowed. Kill a running tool first.",
        )

    args = (payload or {}).get("args", [])
    env_extra = (payload or {}).get("env", {})

    # Audit log
    logger.info(f"[AUDIT] Tool launch requested: tool_id={tool_id}, args={args}")

    try:
        result = await tools_runner.run_tool(tool_id, args=args, env_extra=env_extra)
        logger.info(f"[AUDIT] Tool started: tool_id={tool_id}, run_id={result.get('run_id')}, pid={result.get('pid')}")
        return result
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/tools/status/{run_id}")
async def get_tool_status(run_id: str) -> dict[str, Any]:
    """Get status and output of a running tool."""
    status = tools_runner.get_tool_status(run_id)
    if not status:
        raise HTTPException(status_code=404, detail="Run not found")
    return status


@router.post("/tools/kill/{run_id}", dependencies=[Depends(require_operator)])
async def kill_tool(run_id: str) -> dict[str, Any]:
    """Kill a running tool process."""
    killed = tools_runner.kill_tool(run_id)
    if not killed:
        raise HTTPException(status_code=404, detail="Run not found or already stopped")
    logger.info(f"[AUDIT] Tool killed: run_id={run_id}")
    return {"ok": True, "run_id": run_id}


# ─── Package Installer (Hardened) ────────────────────────────────────────

@router.post("/packages/install", dependencies=[Depends(require_operator)])
async def install_package(payload: dict[str, str]) -> dict[str, Any]:
    """
    Install a Python package into the backend environment.

    Security measures:
    - Package name validated against PyPI naming conventions
    - Blocked packages list enforced
    - Rate limited to 5 installs per minute
    - 120s timeout on pip process
    """
    package = _validate_package_name(payload.get("package", ""))
    _check_install_rate_limit()

    logger.info(f"[AUDIT] Package install requested: {package}")

    cmd = [sys.executable, "-m", "pip", "install", package, "--quiet"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        ok = proc.returncode == 0

        logger.info(f"[AUDIT] Package install {'succeeded' if ok else 'failed'}: {package} (rc={proc.returncode})")

        return {
            "ok": ok,
            "package": package,
            "return_code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace")[-2000:],
            "stderr": stderr.decode("utf-8", errors="replace")[-2000:],
        }
    except asyncio.TimeoutError:
        logger.warning(f"[AUDIT] Package install timed out: {package}")
        raise HTTPException(status_code=408, detail="pip install timed out after 120s")
