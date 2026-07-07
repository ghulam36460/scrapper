# -*- coding: utf-8 -*-
"""ASAGUS co-engine integration for Agent Reach.

This module is the Agent Reach side of the ASAGUS MAX mode contract.  It
keeps the real scraping/command orchestration inside Agent Reach while the
outer ``Download/asagus_tool_launcher.py`` remains a generic subprocess
launcher.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


TOOL_ROOT = Path(__file__).resolve().parents[2]
DOWNLOAD_ROOT = TOOL_ROOT.parent
DEFAULT_RUNS_ROOT = DOWNLOAD_ROOT / ".asagus-runs"
ASAGUS_MANIFEST = TOOL_ROOT / "config" / "asagus.json"

UNIFIED_FIELDNAMES = [
    "name",
    "category",
    "phone",
    "whatsapp",
    "email",
    "address",
    "city",
    "country_code",
    "lat",
    "lng",
    "website_url",
    "facebook_url",
    "instagram_url",
    "twitter_url",
    "linkedin_url",
    "rating",
    "review_count",
    "source_tool",
    "source_url",
    "description",
]

ASAGUS_DEPENDENCIES = [
    {"module": "requests", "requirement": "requests>=2.28"},
    {"module": "feedparser", "requirement": "feedparser>=6.0"},
    {"module": "dotenv", "requirement": "python-dotenv>=1.0"},
    {"module": "loguru", "requirement": "loguru>=0.7"},
    {"module": "yaml", "requirement": "pyyaml>=6.0"},
    {"module": "rich", "requirement": "rich>=13.0"},
    {"module": "yt_dlp", "requirement": "yt-dlp>=2024.0"},
]


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _json_safe_excerpt(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit // 2] + "\n...[truncated]...\n" + text[-limit // 2 :]


def _prepend_path(directory: Path) -> None:
    if not directory.exists():
        return
    current = os.environ.get("PATH", "")
    parts = current.split(os.pathsep) if current else []
    value = str(directory)
    if value not in parts:
        os.environ["PATH"] = value + (os.pathsep + current if current else "")


def _load_asagus_manifest() -> dict[str, Any]:
    try:
        payload = json.loads(ASAGUS_MANIFEST.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _backend_python_from_env() -> Path:
    configured = os.environ.get("ASAGUS_BACKEND_PYTHON", "")
    if configured:
        return Path(configured).expanduser().absolute()
    return Path(sys.executable).absolute()


def _install_requirement(python_executable: Path, requirement: str, timeout: int) -> dict[str, Any]:
    command = [str(python_executable), "-m", "pip", "install", requirement]
    started = time.time()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return {
            "requirement": requirement,
            "command": " ".join(command),
            "return_code": result.returncode,
            "ok": result.returncode == 0,
            "stdout": _json_safe_excerpt(result.stdout or ""),
            "stderr": _json_safe_excerpt(result.stderr or ""),
            "elapsed_seconds": round(time.time() - started, 3),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "requirement": requirement,
            "command": " ".join(command),
            "return_code": None,
            "ok": False,
            "stdout": _json_safe_excerpt(exc.stdout or ""),
            "stderr": _json_safe_excerpt(exc.stderr or ""),
            "elapsed_seconds": round(time.time() - started, 3),
            "error": f"timed out after {timeout}s",
        }
    except Exception as exc:
        return {
            "requirement": requirement,
            "command": " ".join(command),
            "return_code": None,
            "ok": False,
            "elapsed_seconds": round(time.time() - started, 3),
            "error": str(exc),
        }


def _module_available_in_python(python_executable: Path, module: str) -> bool:
    if python_executable == Path(sys.executable).absolute():
        return importlib.util.find_spec(module) is not None
    try:
        result = subprocess.run(
            [
                str(python_executable),
                "-c",
                (
                    "import importlib.util, sys; "
                    f"sys.exit(0 if importlib.util.find_spec({module!r}) else 1)"
                ),
            ],
            capture_output=True,
            timeout=20,
        )
        return result.returncode == 0
    except Exception:
        return False


def _ensure_ytdlp_node_runtime() -> dict[str, Any]:
    node = shutil.which("node")
    if not node:
        return {"name": "yt-dlp-js-runtime", "ok": False, "skipped": True, "reason": "node not found"}
    config_path = Path.home() / ".config" / "yt-dlp" / "config"
    line = "--js-runtimes node"
    try:
        existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        if line in existing:
            return {"name": "yt-dlp-js-runtime", "ok": True, "changed": False, "path": str(config_path)}
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("a", encoding="utf-8") as handle:
            if existing and not existing.endswith("\n"):
                handle.write("\n")
            handle.write(line + "\n")
        return {"name": "yt-dlp-js-runtime", "ok": True, "changed": True, "path": str(config_path)}
    except Exception as exc:
        return {"name": "yt-dlp-js-runtime", "ok": False, "error": str(exc), "path": str(config_path)}


def ensure_asagus_backend_dependencies(
    *,
    backend_python: Path | str | None = None,
    auto_install: bool | None = None,
    timeout_seconds: int = 240,
) -> dict[str, Any]:
    """Ensure Agent Reach runtime dependencies exist in the ASAGUS backend venv."""

    python_executable = Path(backend_python).expanduser().absolute() if backend_python else _backend_python_from_env()
    if not python_executable.exists():
        python_executable = Path(sys.executable).absolute()

    _prepend_path(python_executable.parent)

    should_install = _truthy(os.environ.get("ASAGUS_AGENT_REACH_AUTO_INSTALL"), True) if auto_install is None else auto_install
    before_missing = [
        item
        for item in ASAGUS_DEPENDENCIES
        if not _module_available_in_python(python_executable, item["module"])
    ]

    installs: list[dict[str, Any]] = []
    if before_missing and should_install:
        for item in before_missing:
            installs.append(_install_requirement(python_executable, item["requirement"], timeout_seconds))
        importlib.invalidate_caches()

    post_install_actions: list[dict[str, Any]] = []
    if _module_available_in_python(python_executable, "yt_dlp"):
        post_install_actions.append(_ensure_ytdlp_node_runtime())

    after_missing = [
        item
        for item in ASAGUS_DEPENDENCIES
        if not _module_available_in_python(python_executable, item["module"])
    ]
    post_install_ok = all(action.get("ok", False) or action.get("skipped", False) for action in post_install_actions)
    return {
        "backend_python": str(python_executable),
        "venv_bin": str(python_executable.parent),
        "auto_install": should_install,
        "dependencies_checked": [item["requirement"] for item in ASAGUS_DEPENDENCIES],
        "missing_before": [item["requirement"] for item in before_missing],
        "install_attempts": installs,
        "post_install_actions": post_install_actions,
        "missing_after": [item["requirement"] for item in after_missing],
        "ok": not after_missing and all(item.get("ok", True) for item in installs) and post_install_ok,
    }


@dataclass
class AsagusJobContext:
    job_id: str = "manual"
    query: str = ""
    location: str = ""
    limit: int = 25
    mode: str = "balanced"
    website_filter: str = "all"
    tool_id: str = "agent-reach"
    real_run: bool = False
    runs_root: Path = DEFAULT_RUNS_ROOT
    output_dir: Path | None = None
    requested_channels: list[str] = field(default_factory=list)
    max_results: int = 25
    dependency_bootstrap: bool = True

    @classmethod
    def from_env(cls) -> "AsagusJobContext":
        limit = _safe_int(os.environ.get("ASAGUS_LIMIT"), 25)
        max_results = min(max(_safe_int(os.environ.get("ASAGUS_TOOL_MAX_RESULTS"), limit), 1), 100)
        runs_root = Path(os.environ.get("ASAGUS_RUNS_ROOT", str(DEFAULT_RUNS_ROOT))).expanduser()
        channels = [
            item.strip()
            for item in os.environ.get("ASAGUS_AGENT_REACH_CHANNELS", "").split(",")
            if item.strip()
        ]
        context = cls(
            job_id=os.environ.get("ASAGUS_JOB_ID", "manual"),
            query=os.environ.get("ASAGUS_QUERY", ""),
            location=os.environ.get("ASAGUS_LOCATION", ""),
            limit=limit,
            mode=os.environ.get("ASAGUS_MODE", "balanced"),
            website_filter=os.environ.get("ASAGUS_WEBSITE_FILTER", "all"),
            tool_id=os.environ.get("ASAGUS_TOOL_ID", "agent-reach") or "agent-reach",
            real_run=os.environ.get("ASAGUS_TOOL_REAL_RUN", "0") == "1",
            runs_root=runs_root,
            requested_channels=channels,
            max_results=max_results,
            dependency_bootstrap=_truthy(os.environ.get("ASAGUS_AGENT_REACH_BOOTSTRAP"), True),
        )
        context.output_dir = runs_root / context.job_id
        return context

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "AsagusJobContext":
        env_context = cls.from_env()
        context = cls(
            job_id=args.job_id or env_context.job_id,
            query=args.query or env_context.query,
            location=args.location or env_context.location,
            limit=args.limit or env_context.limit,
            mode=args.mode or env_context.mode,
            website_filter=args.website_filter or env_context.website_filter,
            tool_id="agent-reach",
            real_run=bool(args.real_run),
            runs_root=Path(args.runs_root).expanduser() if args.runs_root else env_context.runs_root,
            requested_channels=[
                item.strip()
                for item in (args.channels or "").split(",")
                if item.strip()
            ],
            max_results=min(max(args.max_results or env_context.max_results, 1), 100),
            dependency_bootstrap=not args.no_bootstrap,
        )
        context.output_dir = context.runs_root / context.job_id
        return context

    def normalized(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["runs_root"] = str(self.runs_root)
        payload["output_dir"] = str(self.output_dir or self.runs_root / self.job_id)
        return payload


class AsagusCoEngine:
    """Run Agent Reach channels against an ASAGUS job context."""

    SEARCH_URLS = (
        "https://duckduckgo.com/html/?q={query}",
        "https://www.google.com/search?q={query}",
    )
    EXCLUDED_DOMAINS = {
        "google.com",
        "www.google.com",
        "duckduckgo.com",
        "www.duckduckgo.com",
        "r.jina.ai",
        "jina.ai",
        "bing.com",
        "www.bing.com",
        "youtube.com",
        "www.youtube.com",
        "youtu.be",
        "facebook.com",
        "www.facebook.com",
        "instagram.com",
        "www.instagram.com",
        "x.com",
        "twitter.com",
        "www.twitter.com",
        "linkedin.com",
        "www.linkedin.com",
        "wikipedia.org",
        "www.wikipedia.org",
        "yelp.com",
        "www.yelp.com",
        "tripadvisor.com",
        "www.tripadvisor.com",
    }
    FILE_SUFFIXES = (
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".svg",
        ".webp",
        ".pdf",
        ".zip",
        ".mp4",
        ".mp3",
    )

    def __init__(
        self,
        context: AsagusJobContext | None = None,
        *,
        bootstrap_dependencies: bool | None = None,
    ) -> None:
        self.context = context or AsagusJobContext.from_env()
        self.output_dir = self.context.output_dir or self.context.runs_root / self.context.job_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.output_dir / f"{self.context.tool_id}.csv"
        self.json_path = self.output_dir / f"{self.context.tool_id}.json"
        self.dependency_status: dict[str, Any] = {"ok": True, "skipped": True}
        should_bootstrap = self.context.dependency_bootstrap if bootstrap_dependencies is None else bootstrap_dependencies
        if should_bootstrap:
            self.dependency_status = ensure_asagus_backend_dependencies()

        self.available = False
        self.import_error = ""
        self.config = None
        self.web_channel = None
        self._import_agent_reach()
        self.channel_status = self._channel_status()
        self.requested_channels = self._requested_channels()

    def _import_agent_reach(self) -> None:
        try:
            from agent_reach.config import Config
            from agent_reach.channels.web import WebChannel

            self.config = Config()
            self.web_channel = WebChannel()
            self.available = True
        except Exception as exc:
            self.available = False
            self.import_error = str(exc)

    def _channel_status(self) -> dict[str, Any]:
        if not self.available:
            return {
                "available": False,
                "error": self.import_error or "Agent Reach could not be imported",
                "channels": {},
                "ready_channels": [],
                "ready_count": 0,
                "total_channels": 0,
            }
        try:
            from agent_reach.doctor import check_all

            results = check_all(self.config)
            ready = [name for name, data in results.items() if data.get("status") == "ok"]
            return {
                "available": True,
                "channels": {
                    name: {
                        "status": data.get("status"),
                        "message": data.get("message"),
                        "backends": data.get("backends", []),
                        "tier": data.get("tier"),
                    }
                    for name, data in results.items()
                },
                "ready_channels": ready,
                "ready_count": len(ready),
                "total_channels": len(results),
            }
        except Exception as exc:
            return {
                "available": False,
                "error": str(exc),
                "channels": {},
                "ready_channels": [],
                "ready_count": 0,
                "total_channels": 0,
            }

    def _requested_channels(self) -> list[str]:
        ready = set(self.channel_status.get("ready_channels", []))
        requested = [name for name in self.context.requested_channels if name in ready]
        return requested or sorted(ready)

    def _credential_env(self) -> dict[str, str]:
        env: dict[str, str] = {}
        if not self.config:
            return env
        for config_key, env_key in (
            ("github_token", "GH_TOKEN"),
            ("twitter_auth_token", "TWITTER_AUTH_TOKEN"),
            ("twitter_ct0", "TWITTER_CT0"),
            ("groq_api_key", "GROQ_API_KEY"),
            ("bilibili_proxy", "BILIBILI_PROXY"),
        ):
            try:
                value = self.config.get(config_key)
            except Exception:
                value = None
            if value:
                env[env_key] = str(value)
        return env

    def _command_env(self) -> dict[str, str]:
        env = {**os.environ, **self._credential_env()}
        backend_python = _backend_python_from_env()
        if backend_python.exists():
            parts = env.get("PATH", "")
            venv_bin = str(backend_python.parent)
            if venv_bin not in parts.split(os.pathsep):
                env["PATH"] = venv_bin + (os.pathsep + parts if parts else "")
        return env

    def status(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "integration_config": _load_asagus_manifest(),
            "context": self.context.normalized(),
            "dependency_status": self.dependency_status,
            "channels_status": self.channel_status,
            "channels_requested": self.requested_channels,
            "output_dir": str(self.output_dir),
        }

    def _read_with_agent_reach_web(self, url: str) -> tuple[str | None, str | None]:
        try:
            if self.web_channel is not None:
                return self.web_channel.read(url), None
            return self._jina_read(url), None
        except Exception as exc:
            return None, str(exc)

    @staticmethod
    def _jina_read(url: str) -> str:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        req = urllib.request.Request(
            f"https://r.jina.ai/{url}",
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Accept": "text/plain",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _candidate_queries(self, query: str, location: str) -> list[str]:
        base = " ".join(part for part in [query.strip(), location.strip()] if part)
        return [
            f"{base} official website contact email phone",
            f"{base} business website contact",
            f"{base} address phone email",
        ]

    def discover_business_urls(self, query: str, location: str) -> tuple[list[str], list[dict[str, Any]]]:
        desired = min(max(self.context.max_results * 4, 4), 80)
        urls: list[str] = []
        seen: set[str] = set()
        search_attempts: list[dict[str, Any]] = []

        if "exa_search" in self.requested_channels:
            exa_urls, exa_attempt = self._discover_urls_with_exa(query, location, desired)
            search_attempts.append(exa_attempt)
            for raw_url in exa_urls:
                if self._append_candidate_url(raw_url, urls, seen, desired):
                    return urls, search_attempts

        for candidate_query in self._candidate_queries(query, location):
            encoded = urllib.parse.quote_plus(candidate_query)
            for template in self.SEARCH_URLS:
                search_url = template.format(query=encoded)
                content, error = self._read_with_agent_reach_web(search_url)
                extracted = self._extract_urls(content or "")
                search_attempts.append(
                    {
                        "source": urllib.parse.urlparse(search_url).netloc,
                        "query": candidate_query,
                        "url": search_url,
                        "ok": bool(content),
                        "error": error,
                        "urls_found": len(extracted),
                    }
                )
                for raw_url in extracted:
                    if self._append_candidate_url(raw_url, urls, seen, desired):
                        return urls, search_attempts

        return urls, search_attempts

    def _append_candidate_url(self, raw_url: str, urls: list[str], seen: set[str], desired: int) -> bool:
        clean_url = self._clean_candidate_url(raw_url)
        if not clean_url or not self._is_business_candidate(clean_url):
            return False
        key = self._domain_key(clean_url)
        if key in seen:
            return False
        seen.add(key)
        urls.append(clean_url)
        return len(urls) >= desired

    def _discover_urls_with_exa(self, query: str, location: str, desired: int) -> tuple[list[str], dict[str, Any]]:
        candidate_query = " ".join(part for part in [query.strip(), location.strip(), "official website contact"] if part)
        attempt: dict[str, Any] = {
            "channel": "exa_search",
            "source": "exa_search",
            "query": candidate_query,
            "ok": False,
            "urls_found": 0,
        }
        call = f'exa.web_search_exa(query: "{self._escape_mcp(candidate_query)}", numResults: {min(max(desired, 1), 25)})'
        result = self._run_command(["mcporter", "call", call], timeout=45)
        output = (result.get("stdout") or "") + "\n" + (result.get("stderr") or "")
        urls = self._extract_urls(output)
        attempt.update(
            {
                "ok": bool(result.get("ok")),
                "return_code": result.get("return_code"),
                "urls_found": len(urls),
                "error": "" if result.get("ok") else output[-500:],
                "command": result.get("command"),
            }
        )
        return urls, attempt

    def run_auxiliary_channels(self, query: str, urls: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
        used: list[str] = []
        attempts: list[dict[str, Any]] = []
        limit = min(max(self.context.max_results, 1), 10)

        command_plan = self._command_plan(query, limit)
        for channel in self.requested_channels:
            if channel in {"web", "exa_search", "rss", "v2ex", "xueqiu"}:
                continue
            command = command_plan.get(channel)
            if not command:
                continue
            result = self._run_command(command, timeout=60)
            result["channel"] = channel
            attempts.append(result)
            used.append(channel)

        if "rss" in self.requested_channels:
            attempts.extend(self._attempt_rss_feeds(urls[: min(len(urls), 12)]))
            used.append("rss")

        if "v2ex" in self.requested_channels:
            attempts.append(self._attempt_v2ex(query, limit))
            used.append("v2ex")

        if "xueqiu" in self.requested_channels:
            attempts.append(self._attempt_xueqiu(query, limit))
            used.append("xueqiu")

        return sorted(set(used)), attempts

    def _command_plan(self, query: str, limit: int) -> dict[str, list[str]]:
        quoted = self._escape_mcp(query)
        return {
            "github": ["gh", "search", "repos", query, "--sort", "stars", "--limit", str(limit)],
            "youtube": ["yt-dlp", "--simulate", "--flat-playlist", "--dump-single-json", f"ytsearch{limit}:{query}"],
            "reddit": ["rdt", "search", query, "--limit", str(limit)],
            "twitter": ["twitter", "search", query, "-n", str(limit), "--json"],
            "xiaohongshu": ["xhs", "search", query],
            "bilibili": ["yt-dlp", "--simulate", "--flat-playlist", "--dump-single-json", f"bilisearch{limit}:{query}"],
            "weibo": ["mcporter", "call", f'weibo.search_content(keyword: "{quoted}", limit: {limit})'],
            "wechat": ["mcporter", "call", f'exa.web_search_exa(query: "{quoted} site:mp.weixin.qq.com", numResults: {limit})'],
            "linkedin": ["mcporter", "call", f'linkedin.search_people(keyword: "{quoted}", limit: {limit})'],
        }

    def _run_command(self, command: list[str], *, timeout: int) -> dict[str, Any]:
        started = time.time()
        binary = shutil.which(command[0], path=self._command_env().get("PATH"))
        if not binary:
            return {
                "command": " ".join(command),
                "ok": False,
                "return_code": None,
                "stdout": "",
                "stderr": f"{command[0]} not found",
                "elapsed_seconds": 0,
            }
        actual = [binary, *command[1:]]
        try:
            result = subprocess.run(
                actual,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=self._command_env(),
            )
            return {
                "command": " ".join(command),
                "ok": result.returncode == 0,
                "return_code": result.returncode,
                "stdout": _json_safe_excerpt(result.stdout or ""),
                "stderr": _json_safe_excerpt(result.stderr or ""),
                "elapsed_seconds": round(time.time() - started, 3),
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "command": " ".join(command),
                "ok": False,
                "return_code": None,
                "stdout": _json_safe_excerpt(exc.stdout or ""),
                "stderr": _json_safe_excerpt(exc.stderr or ""),
                "elapsed_seconds": round(time.time() - started, 3),
                "error": f"timed out after {timeout}s",
            }
        except Exception as exc:
            return {
                "command": " ".join(command),
                "ok": False,
                "return_code": None,
                "stdout": "",
                "stderr": str(exc),
                "elapsed_seconds": round(time.time() - started, 3),
            }

    def _attempt_rss_feeds(self, urls: list[str]) -> list[dict[str, Any]]:
        attempts: list[dict[str, Any]] = []
        try:
            import feedparser
        except ImportError as exc:
            return [{"channel": "rss", "ok": False, "error": str(exc), "feeds_checked": 0}]

        feed_paths = ("/feed", "/rss.xml", "/atom.xml")
        checked = 0
        max_domains = max(2, min(5, self.context.max_results))
        for url in urls[:max_domains]:
            if checked >= 15:
                break
            parsed = urllib.parse.urlparse(url)
            if not parsed.netloc:
                continue
            base = urllib.parse.urlunparse((parsed.scheme or "https", parsed.netloc, "", "", "", ""))
            for path in feed_paths:
                if checked >= 15:
                    break
                feed_url = base.rstrip("/") + path
                started = time.time()
                try:
                    req = urllib.request.Request(feed_url, headers={"User-Agent": "agent-reach-asagus/1.0"})
                    with urllib.request.urlopen(req, timeout=5) as response:
                        feed = feedparser.parse(response.read())
                    entries = getattr(feed, "entries", []) or []
                    attempts.append(
                        {
                            "channel": "rss",
                            "url": feed_url,
                            "ok": bool(entries),
                            "entries": [
                                {
                                    "title": getattr(entry, "title", ""),
                                    "link": getattr(entry, "link", ""),
                                }
                                for entry in entries[:3]
                            ],
                            "elapsed_seconds": round(time.time() - started, 3),
                        }
                    )
                except Exception as exc:
                    attempts.append(
                        {
                            "channel": "rss",
                            "url": feed_url,
                            "ok": False,
                            "error": str(exc),
                            "elapsed_seconds": round(time.time() - started, 3),
                        }
                    )
                checked += 1
        return attempts or [{"channel": "rss", "ok": False, "feeds_checked": 0}]

    def _attempt_v2ex(self, query: str, limit: int) -> dict[str, Any]:
        started = time.time()
        try:
            from agent_reach.channels.v2ex import V2EXChannel

            topics = V2EXChannel().get_hot_topics(limit=limit)
            return {
                "channel": "v2ex",
                "ok": True,
                "query": query,
                "records": topics,
                "elapsed_seconds": round(time.time() - started, 3),
            }
        except Exception as exc:
            return {
                "channel": "v2ex",
                "ok": False,
                "query": query,
                "error": str(exc),
                "elapsed_seconds": round(time.time() - started, 3),
            }

    def _attempt_xueqiu(self, query: str, limit: int) -> dict[str, Any]:
        started = time.time()
        try:
            from agent_reach.channels.xueqiu import XueqiuChannel

            channel = XueqiuChannel()
            stocks = channel.search_stock(query, limit=limit)
            return {
                "channel": "xueqiu",
                "ok": True,
                "query": query,
                "records": stocks,
                "elapsed_seconds": round(time.time() - started, 3),
            }
        except Exception as exc:
            return {
                "channel": "xueqiu",
                "ok": False,
                "query": query,
                "error": str(exc),
                "elapsed_seconds": round(time.time() - started, 3),
            }

    @staticmethod
    def _escape_mcp(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    @staticmethod
    def _extract_urls(text: str) -> list[str]:
        if not text:
            return []
        urls: list[str] = []
        patterns = [
            r"\[[^\]]+\]\((https?://[^)\s]+)\)",
            r"href=[\"'](https?://[^\"']+)[\"']",
            r"https?://[^\s)\]\"'<>]+",
        ]
        for pattern in patterns:
            urls.extend(re.findall(pattern, text, flags=re.IGNORECASE))
        return urls

    def _clean_candidate_url(self, url: str) -> str:
        url = urllib.parse.unquote(url.strip().strip(".,;:)]}'\""))
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc.endswith("duckduckgo.com"):
            query = urllib.parse.parse_qs(parsed.query)
            if query.get("uddg"):
                url = query["uddg"][0]
                parsed = urllib.parse.urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return ""
        netloc = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path or "/"
        cleaned = urllib.parse.urlunparse((parsed.scheme, netloc, path, "", "", ""))
        return cleaned.rstrip("/")

    @staticmethod
    def _domain_key(url: str) -> str:
        return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")

    def _is_business_candidate(self, url: str) -> bool:
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.lower().removeprefix("www.")
        if not domain or domain in self.EXCLUDED_DOMAINS:
            return False
        if any(domain == excluded or domain.endswith(f".{excluded}") for excluded in self.EXCLUDED_DOMAINS):
            return False
        if parsed.path.lower().endswith(self.FILE_SUFFIXES):
            return False
        return "." in domain

    def extract_business_data(self, content: str, url: str) -> dict[str, Any]:
        domain = self._domain_key(url)
        title = self._extract_title(content) or domain.split(".")[0].replace("-", " ").title()
        emails = self._extract_emails(content)
        phones = self._extract_phones(content)
        social = self._extract_social_links(content)

        return {
            "business_name": title,
            "name": title,
            "email": emails[0] if emails else "",
            "phone": phones[0] if phones else "",
            "website_url": url,
            "address": self._extract_address(content),
            "description": self._extract_description(content),
            "source_url": url,
            "source_tool": self.context.tool_id,
            "facebook_url": social.get("facebook", ""),
            "instagram_url": social.get("instagram", ""),
            "twitter_url": social.get("twitter", ""),
            "linkedin_url": social.get("linkedin", ""),
            "agent_reach_channel": "web",
            "agent_reach_backend": "Jina Reader",
            "agent_reach_content_length": len(content),
            "agent_reach_emails_found": len(emails),
            "agent_reach_phones_found": len(phones),
        }

    @staticmethod
    def _extract_title(text: str) -> str:
        patterns = [
            r"^Title:\s*(.+)$",
            r"^#\s+(.+)$",
            r"^##\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
            if match:
                title = re.sub(r"\s+", " ", match.group(1)).strip()
                if title and len(title) <= 120:
                    return title
        return ""

    @staticmethod
    def _extract_emails(text: str) -> list[str]:
        raw = re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)
        blocked = ("example.", "domain.", "email.", "sentry.", "schema.org", "wixpress.com")
        emails: list[str] = []
        for item in raw:
            email = item.strip(".,;:)]}'\"").lower()
            if any(token in email for token in blocked):
                continue
            if email.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                continue
            if email not in emails:
                emails.append(email)
        return emails[:5]

    @staticmethod
    def _extract_phones(text: str) -> list[str]:
        phones: list[str] = []
        pattern = re.compile(r"(?:\+\d{1,4}[\s().-]?)?(?:\(?\d{2,4}\)?[\s().-]?){2,5}\d{2,4}")
        for match in pattern.finditer(text):
            candidate = match.group(0)
            cleaned = re.sub(r"\s+", " ", candidate).strip(" .,-()")
            digits = re.sub(r"\D", "", cleaned)
            if not (7 <= len(digits) <= 15):
                continue
            if len(set(digits)) < 3:
                continue
            if digits.startswith(("000", "123456")):
                continue
            context = text[max(0, match.start() - 40): match.end() + 40].lower()
            has_phone_shape = any(char in cleaned for char in "+()- ") or "." in cleaned or "-" in cleaned
            has_phone_cue = any(cue in context for cue in ("phone", "tel", "call", "mobile", "whatsapp", "contact"))
            if not has_phone_shape and not has_phone_cue:
                continue
            if cleaned not in phones:
                phones.append(cleaned)
        return phones[:5]

    @staticmethod
    def _extract_social_links(text: str) -> dict[str, str]:
        social: dict[str, str] = {}
        for url in AsagusCoEngine._extract_urls(text):
            clean = url.strip(".,;:)]}'\"")
            domain = urllib.parse.urlparse(clean).netloc.lower()
            if "facebook.com" in domain and "facebook" not in social:
                social["facebook"] = clean
            elif "instagram.com" in domain and "instagram" not in social:
                social["instagram"] = clean
            elif ("twitter.com" in domain or "x.com" in domain) and "twitter" not in social:
                social["twitter"] = clean
            elif "linkedin.com" in domain and "linkedin" not in social:
                social["linkedin"] = clean
        return social

    @staticmethod
    def _extract_address(text: str) -> str:
        patterns = [
            r"\b\d{1,6}\s+[A-Za-z0-9 .'-]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Way|Plaza)\b[^.\n\]]{0,80}",
            r"\b(?:Doha|Dubai|Abu Dhabi|Sharjah|Qatar|UAE)\b[^.\n\]]{0,100}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                address = re.sub(r"\[[^\]]*\]\([^)]*\)", "", match.group(0))
                address = re.sub(r"\s+", " ", address).strip(" ,")
                if re.match(r"^(?:19|20)\d{2}\b", address):
                    continue
                return address
        return ""

    @staticmethod
    def _extract_description(text: str) -> str:
        for line in text.splitlines():
            clean = re.sub(r"\s+", " ", line).strip()
            if not clean or clean.startswith(("#", "Title:", "URL Source:")):
                continue
            if clean.startswith(("![", "[", "* [", "- [")):
                continue
            if re.fullmatch(r"(?:[*-]\s*)?\[[^\]]+\]\([^)]+\)", clean):
                continue
            if len(clean) < 40:
                continue
            return clean[:300]
        return ""

    @staticmethod
    def _useful_record(record: dict[str, Any]) -> bool:
        return bool(record.get("website_url") and (record.get("name") or record.get("email") or record.get("phone")))

    def _normalize_record(self, record: dict[str, Any]) -> dict[str, Any]:
        normalized = {field: "" for field in UNIFIED_FIELDNAMES}
        normalized["source_tool"] = self.context.tool_id
        field_mappings = {
            "business_name": "name",
            "title": "name",
            "company_name": "name",
            "business": "name",
            "place_name": "name",
            "phone_number": "phone",
            "telephone": "phone",
            "tel": "phone",
            "contact_number": "phone",
            "email_address": "email",
            "contact_email": "email",
            "website": "website_url",
            "url": "website_url",
            "site": "website_url",
            "facebook": "facebook_url",
            "instagram": "instagram_url",
            "twitter": "twitter_url",
            "x_url": "twitter_url",
            "linkedin": "linkedin_url",
            "reviews": "review_count",
            "reviews_count": "review_count",
            "total_reviews": "review_count",
            "about": "description",
        }
        for original_key, value in record.items():
            if value in (None, ""):
                continue
            key_lower = str(original_key).lower().replace("-", "_").replace(" ", "_")
            mapped_key = field_mappings.get(key_lower, key_lower)
            if mapped_key in normalized and not normalized[mapped_key]:
                normalized[mapped_key] = str(value).strip()
        return normalized

    def _save_records_csv(self, records: list[dict[str, Any]]) -> str:
        # Improved normalization for cleaner data
        normalized_records = []
        for record in records:
            norm = self._normalize_record(record)
            # Trim whitespace from all values for cleaner look
            cleaned_record = {k: str(v).strip() for k, v in norm.items()}
            normalized_records.append(cleaned_record)
        
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Using a more robust approach for professional CSV generation
        with self.csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            # Add BOM (utf-8-sig) to ensure Excel opens it correctly with UTF-8 encoding
            writer = csv.DictWriter(
                handle, 
                fieldnames=UNIFIED_FIELDNAMES, 
                extrasaction="ignore",
                quoting=csv.QUOTE_MINIMAL
            )
            writer.writeheader()
            writer.writerows(normalized_records)
        return str(self.csv_path)

    def save_metadata_json(self, metadata: dict[str, Any]) -> None:
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.json_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.json_path)

    def run(self) -> dict[str, Any]:
        start = time.time()
        query = self.context.query or "business"
        location = self.context.location or ""

        metadata: dict[str, Any] = {
            "tool_id": self.context.tool_id,
            "adapter": "agent_reach.integrations.asagus",
            "integration_level": "agent_reach_native_asagus_co_engine",
            "status": "running",
            "dry_run": not self.context.real_run,
            "mode": self.context.mode,
            "job_context": self.context.normalized(),
            "dependency_status": self.dependency_status,
            "agent_reach_available": self.available,
            "channels_status": self.channel_status,
            "channels_requested": self.requested_channels,
            "channels_used": [],
        }

        if not self.context.real_run:
            metadata.update(
                {
                    "status": "dry_run",
                    "message": "Dry run validated Agent Reach availability, dependency bootstrap, and channel readiness.",
                    "records_found": 0,
                    "output_csv": None,
                    "elapsed_seconds": round(time.time() - start, 3),
                }
            )
            self.save_metadata_json(metadata)
            return metadata

        try:
            discovered_urls, search_attempts = self.discover_business_urls(query, location)
            auxiliary_used, auxiliary_attempts = self.run_auxiliary_channels(query, discovered_urls)
            records: list[dict[str, Any]] = []
            scrape_attempts: list[dict[str, Any]] = []
            seen_domains: set[str] = set()

            for url in discovered_urls:
                if len(records) >= self.context.max_results:
                    break
                content, error = self._read_with_agent_reach_web(url)
                attempt = {
                    "channel": "web",
                    "url": url,
                    "ok": bool(content),
                    "error": error,
                    "content_length": len(content or ""),
                }
                scrape_attempts.append(attempt)
                if not content:
                    continue

                record = self.extract_business_data(content, url)
                domain = self._domain_key(url)
                if domain in seen_domains or not self._useful_record(record):
                    continue
                seen_domains.add(domain)
                records.append(record)

            output_csv = self._save_records_csv(records)
            status = "completed" if records else "completed_no_records"
            channels_used = set(auxiliary_used)
            if scrape_attempts:
                channels_used.add("web")
            if any(attempt.get("source") == "exa_search" and attempt.get("ok") for attempt in search_attempts):
                channels_used.add("exa_search")
            metadata.update(
                {
                    "status": status,
                    "message": f"Agent Reach completed with {len(records)} records",
                    "records_found": len(records),
                    "urls_discovered": len(discovered_urls),
                    "urls_attempted": len(scrape_attempts),
                    "search_attempts": search_attempts,
                    "scrape_attempts": scrape_attempts,
                    "channel_attempts": auxiliary_attempts,
                    "channels_used": sorted(channels_used),
                    "output_csv": output_csv,
                    "elapsed_seconds": round(time.time() - start, 3),
                }
            )
            self.save_metadata_json(metadata)
            return metadata
        except Exception as exc:
            metadata.update(
                {
                    "status": "failed",
                    "message": str(exc)[:500],
                    "records_found": 0,
                    "elapsed_seconds": round(time.time() - start, 3),
                }
            )
            self.save_metadata_json(metadata)
            return metadata


def run_from_environment() -> dict[str, Any]:
    return AsagusCoEngine(AsagusJobContext.from_env()).run()


def create_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Agent Reach as an ASAGUS co-engine")
    parser.add_argument("action", nargs="?", choices=["status", "doctor", "run"], default="status")
    parser.add_argument("--query", default="")
    parser.add_argument("--location", default="")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--mode", default="max")
    parser.add_argument("--website-filter", default="all")
    parser.add_argument("--job-id", default="")
    parser.add_argument("--runs-root", default="")
    parser.add_argument("--channels", default="")
    parser.add_argument("--max-results", type=int, default=25)
    parser.add_argument("--real-run", action="store_true")
    parser.add_argument("--no-bootstrap", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = create_arg_parser()
    args = parser.parse_args(argv)
    context = AsagusJobContext.from_args(args)
    engine = AsagusCoEngine(context, bootstrap_dependencies=not args.no_bootstrap)
    result = engine.status() if args.action in {"status", "doctor"} else engine.run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") not in {"failed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
