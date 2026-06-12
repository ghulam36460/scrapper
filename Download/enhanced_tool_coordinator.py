"""
Enhanced Tool Coordinator for ASAGUS Download Tools
Ensures all tools work perfectly with proper environment, dependencies, and resource management.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ToolConfig:
    """Configuration for a Download tool."""
    tool_id: str
    tool_dir: Path
    uses_backend_venv: bool
    backend_python: str
    launcher: str
    pipeline_role: str
    node_project: bool = False
    requires_env: list[str] | None = None
    enabled_in_max_mode: bool = True
    dry_run_by_default: bool = False


class ToolDependencyManager:
    """Manages tool dependencies and environment setup."""
    
    def __init__(self, backend_venv_python: Path):
        self.backend_python = backend_venv_python
        
    def check_python_package(self, package: str) -> bool:
        """Check if a Python package is installed."""
        try:
            result = subprocess.run(
                [str(self.backend_python), "-c", f"import {package}"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def check_node_available(self) -> bool:
        """Check if Node.js is installed."""
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def get_missing_dependencies(self, tool: ToolConfig) -> list[str]:
        """Get list of missing dependencies for a tool."""
        missing = []
        
        if tool.node_project and not self.check_node_available():
            missing.append("node")
        
        # Tool-specific Python packages
        package_map = {
            "scrapegraph-ai": ["scrapegraphai"],
            "scrapling": ["scrapling"],
            "scrapy": ["scrapy"],
            "firecrawl": ["firecrawl"],
            "maxun": ["playwright"],
            "maps-scraper": ["playwright"],
            "outreach-scraper": ["playwright"],
        }
        
        if tool.tool_id in package_map:
            for pkg in package_map[tool.tool_id]:
                if not self.check_python_package(pkg):
                    missing.append(pkg)
        
        return missing


class BrowserPoolCoordinator:
    """Coordinates browser instances across tools to prevent resource conflicts."""
    
    def __init__(self, max_concurrent_browsers: int = 2):
        self.max_concurrent_browsers = max_concurrent_browsers
        self.active_browsers: set[str] = set()
        self._lock = asyncio.Lock()
    
    async def acquire_browser_slot(self, tool_id: str, timeout: float = 300) -> bool:
        """Acquire a browser slot for a tool. Returns False if timeout."""
        start_time = asyncio.get_event_loop().time()
        
        while True:
            async with self._lock:
                if len(self.active_browsers) < self.max_concurrent_browsers:
                    self.active_browsers.add(tool_id)
                    return True
            
            # Check timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                return False
            
            # Wait and retry
            await asyncio.sleep(2)
    
    async def release_browser_slot(self, tool_id: str):
        """Release a browser slot."""
        async with self._lock:
            self.active_browsers.discard(tool_id)


class EnhancedToolCoordinator:
    """Main coordinator for all Download tools."""
    
    # Tools that use browser/Playwright
    BROWSER_TOOLS = {"maps-scraper", "outreach-scraper", "maxun"}
    
    # Tools that need LLM config
    LLM_TOOLS = {"scrapegraph-ai", "agent-reach"}
    
    def __init__(
        self,
        download_root: Path | None = None,
        backend_root: Path | None = None,
        max_concurrent_browsers: int = 2,
    ):
        if download_root is None:
            download_root = Path(__file__).resolve().parent
        if backend_root is None:
            backend_root = download_root.parent / "asagus-scraper-v3" / "backend"
        
        self.download_root = download_root
        self.backend_root = backend_root
        self.backend_python = backend_root / ".venv" / "bin" / "python"
        
        self.dependency_manager = ToolDependencyManager(self.backend_python)
        self.browser_pool = BrowserPoolCoordinator(max_concurrent_browsers)
        
        self.tools = self._discover_tools()
    
    def _discover_tools(self) -> dict[str, ToolConfig]:
        """Discover all tools with .asagus/config.json."""
        tools = {}
        
        for item in self.download_root.iterdir():
            if not item.is_dir() or item.name.startswith("."):
                continue
            
            config_path = item / ".asagus" / "config.json"
            if not config_path.exists():
                continue
            
            try:
                config_data = json.loads(config_path.read_text())
                tool = ToolConfig(
                    tool_id=config_data["tool_id"],
                    tool_dir=item,
                    uses_backend_venv=config_data.get("uses_asagus_backend_venv", True),
                    backend_python=config_data.get("backend_python", ""),
                    launcher=config_data.get("launcher", "../asagus_tool_launcher.py"),
                    pipeline_role=config_data.get("pipeline_role", ""),
                    node_project=config_data.get("node_project", False),
                    requires_env=config_data.get("requires_optional_env"),
                    enabled_in_max_mode=config_data.get("max_mode", {}).get("enabled", True),
                    dry_run_by_default=config_data.get("max_mode", {}).get("dry_run_only_by_default", False),
                )
                tools[tool.tool_id] = tool
            except Exception as e:
                print(f"Warning: Could not load config for {item.name}: {e}")
        
        return tools
    
    def prepare_environment(self, tool: ToolConfig, job_context: dict[str, Any]) -> dict[str, str]:
        """Prepare environment variables for a tool."""
        env = os.environ.copy()
        
        # Job context
        env["ASAGUS_JOB_ID"] = job_context.get("job_id", "manual")
        env["ASAGUS_TOOL_ID"] = tool.tool_id
        env["ASAGUS_QUERY"] = job_context.get("query", "")
        env["ASAGUS_LOCATION"] = job_context.get("location", "")
        env["ASAGUS_LIMIT"] = str(job_context.get("limit", 25))
        env["ASAGUS_MODE"] = job_context.get("mode", "balanced")
        env["ASAGUS_WEBSITE_FILTER"] = job_context.get("website_filter", "all")
        
        # Paths
        env["ASAGUS_BACKEND_ROOT"] = str(self.backend_root)
        env["ASAGUS_BACKEND_PYTHON"] = str(self.backend_python)
        env["ASAGUS_RUNS_ROOT"] = str(self.download_root / ".asagus-runs")
        env["ASAGUS_PIPELINE_CONFIG"] = str(self.download_root / "asagus_pipeline.json")
        
        # Control flags
        if job_context.get("network_enabled", True) and not tool.dry_run_by_default:
            env["ASAGUS_TOOL_REAL_RUN"] = "1"
        else:
            env["ASAGUS_TOOL_REAL_RUN"] = "0"
        
        env["ASAGUS_DRY_RUN"] = "0" if env["ASAGUS_TOOL_REAL_RUN"] == "1" else "1"
        
        # LLM config (for tools that need it)
        if tool.tool_id in self.LLM_TOOLS:
            llm_config = job_context.get("llm_config", {})
            if llm_config.get("provider"):
                env["LLM_PROVIDER"] = llm_config["provider"]
            if llm_config.get("api_key"):
                env["LLM_API_KEY"] = llm_config["api_key"]
            if llm_config.get("model"):
                env["LLM_MODEL"] = llm_config["model"]
            if llm_config.get("base_url"):
                env["LLM_BASE_URL"] = llm_config["base_url"]
            
            # Provider-specific keys
            for key in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"]:
                if key in os.environ:
                    env[key] = os.environ[key]
        
        # Proxy config
        for key in ["RESIDENTIAL_PROXY_URL", "DATACENTER_PROXY_URL"]:
            if key in os.environ:
                env[key] = os.environ[key]
        
        # Tool-specific required env
        if tool.requires_env:
            for key in tool.requires_env:
                if key in os.environ:
                    env[key] = os.environ[key]
        
        return env
    
    async def launch_tool(
        self,
        tool_id: str,
        job_context: dict[str, Any],
        timeout: float = 240,
    ) -> dict[str, Any]:
        """Launch a tool and return its result."""
        tool = self.tools.get(tool_id)
        if not tool:
            return {
                "tool_id": tool_id,
                "status": "not_found",
                "message": f"Tool {tool_id} not found in Download folder",
            }
        
        if not tool.enabled_in_max_mode and job_context.get("mode") == "max":
            return {
                "tool_id": tool_id,
                "status": "disabled_in_mode",
                "message": f"Tool {tool_id} is disabled in max mode",
            }
        
        # Check dependencies
        missing_deps = self.dependency_manager.get_missing_dependencies(tool)
        if missing_deps:
            return {
                "tool_id": tool_id,
                "status": "missing_dependencies",
                "missing": missing_deps,
                "message": f"Missing dependencies: {', '.join(missing_deps)}",
            }
        
        # Check required environment variables
        if tool.requires_env:
            missing_env = [key for key in tool.requires_env if not os.environ.get(key)]
            if missing_env:
                return {
                    "tool_id": tool_id,
                    "status": "missing_env",
                    "missing": missing_env,
                    "message": f"Missing required environment variables: {', '.join(missing_env)}",
                }
        
        # Acquire browser slot if needed
        browser_slot_acquired = False
        if tool.tool_id in self.BROWSER_TOOLS:
            browser_slot_acquired = await self.browser_pool.acquire_browser_slot(tool_id, timeout=60)
            if not browser_slot_acquired:
                return {
                    "tool_id": tool_id,
                    "status": "browser_pool_timeout",
                    "message": "Could not acquire browser slot (too many concurrent browsers)",
                }
        
        try:
            # Prepare environment
            env = self.prepare_environment(tool, job_context)
            
            # Build command
            run_script = tool.tool_dir / "run-asagus.sh"
            if not run_script.exists():
                return {
                    "tool_id": tool_id,
                    "status": "no_run_script",
                    "message": f"run-asagus.sh not found in {tool.tool_dir}",
                }
            
            # Execute
            process = await asyncio.create_subprocess_exec(
                "bash",
                str(run_script),
                cwd=str(tool.tool_dir),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    "tool_id": tool_id,
                    "status": "timeout",
                    "message": f"Tool execution exceeded {timeout}s timeout",
                }
            
            # Parse output
            try:
                output_text = stdout.decode("utf-8", errors="replace")
                # Try to find JSON in output
                for line in output_text.strip().split("\n"):
                    line = line.strip()
                    if line.startswith("{") and line.endswith("}"):
                        try:
                            result = json.loads(line)
                            if isinstance(result, dict) and "tool_id" in result:
                                return result
                        except json.JSONDecodeError:
                            continue
            except Exception:
                pass
            
            # Fallback result
            return {
                "tool_id": tool_id,
                "status": "completed" if process.returncode == 0 else "failed",
                "exit_code": process.returncode,
                "message": f"Tool executed with exit code {process.returncode}",
                "stdout_preview": stdout.decode("utf-8", errors="replace")[-500:],
                "stderr_preview": stderr.decode("utf-8", errors="replace")[-500:],
            }
        
        finally:
            # Release browser slot
            if browser_slot_acquired:
                await self.browser_pool.release_browser_slot(tool_id)
    
    async def launch_all_tools(
        self,
        job_context: dict[str, Any],
        enabled_tool_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Launch all enabled tools for a job."""
        if enabled_tool_ids is None:
            enabled_tool_ids = list(self.tools.keys())
        
        # Launch tools concurrently
        tasks = [
            self.launch_tool(tool_id, job_context)
            for tool_id in enabled_tool_ids
            if tool_id in self.tools
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        tool_results = {}
        for i, tool_id in enumerate(enabled_tool_ids):
            if tool_id not in self.tools:
                continue
            result = results[i]
            if isinstance(result, Exception):
                tool_results[tool_id] = {
                    "tool_id": tool_id,
                    "status": "exception",
                    "message": str(result),
                }
            else:
                tool_results[tool_id] = result
        
        return tool_results
    
    def get_tool_summary(self) -> dict[str, Any]:
        """Get summary of all tools and their status."""
        summary = {
            "total_tools": len(self.tools),
            "tools": {},
        }
        
        for tool_id, tool in self.tools.items():
            missing_deps = self.dependency_manager.get_missing_dependencies(tool)
            missing_env = []
            if tool.requires_env:
                missing_env = [key for key in tool.requires_env if not os.environ.get(key)]
            
            ready = len(missing_deps) == 0 and len(missing_env) == 0
            
            summary["tools"][tool_id] = {
                "tool_dir": str(tool.tool_dir.name),
                "pipeline_role": tool.pipeline_role,
                "node_project": tool.node_project,
                "uses_browser": tool.tool_id in self.BROWSER_TOOLS,
                "needs_llm": tool.tool_id in self.LLM_TOOLS,
                "ready": ready,
                "missing_dependencies": missing_deps,
                "missing_env": missing_env,
                "enabled_in_max_mode": tool.enabled_in_max_mode,
            }
        
        return summary


async def main():
    """CLI entry point for testing."""
    coordinator = EnhancedToolCoordinator()
    
    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        summary = coordinator.get_tool_summary()
        print(json.dumps(summary, indent=2))
        return
    
    # Test launch
    job_context = {
        "job_id": "test-manual",
        "query": "restaurants",
        "location": "Lahore",
        "limit": 10,
        "mode": "max",
        "network_enabled": False,  # Dry run for testing
    }
    
    print("Launching all tools...")
    results = await coordinator.launch_all_tools(job_context)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
