"""
Agent-Reach Service - Backend integration for Agent-Reach configuration and status
"""
from __future__ import annotations

import os
import sys
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

def _find_agent_reach_dir() -> Path:
    """Locate the checked-out Agent-Reach tree from common ASAGUS layouts."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "Download" / "Agent-Reach-main"
        if (candidate / "agent_reach").is_dir():
            return candidate
    return here.parents[4] / "Download" / "Agent-Reach-main"


# Add Agent-Reach to path
AGENT_REACH_DIR = _find_agent_reach_dir()
DOWNLOAD_ROOT = AGENT_REACH_DIR.parent
RUNS_ROOT = DOWNLOAD_ROOT / ".asagus-runs"
BACKEND_BIN = Path(__file__).resolve().parents[2] / ".venv" / "bin"
if BACKEND_BIN.exists():
    current_path = os.environ.get("PATH", "")
    backend_bin = str(BACKEND_BIN)
    if backend_bin not in current_path.split(os.pathsep):
        os.environ["PATH"] = backend_bin + (os.pathsep + current_path if current_path else "")
if str(AGENT_REACH_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_REACH_DIR))

try:
    from agent_reach.config import Config
    from agent_reach.doctor import check_all
    AGENT_REACH_AVAILABLE = True
except ImportError:
    AGENT_REACH_AVAILABLE = False


class AgentReachService:
    """Service for managing Agent-Reach configuration and status"""

    CHANNEL_NAMES = [
        "web", "github", "twitter", "youtube", "reddit", "bilibili",
        "xiaohongshu", "douyin", "linkedin", "wechat", "weibo",
        "xiaoyuzhou", "v2ex", "xueqiu", "rss", "exa_search"
    ]

    AGENT_REACH_INSTALL_CHANNELS = {
        "twitter": "twitter",
        "reddit": "reddit",
        "xiaohongshu": "xiaohongshu",
        "bilibili": "bilibili",
        "weibo": "weibo",
        "wechat": "wechat",
        "xiaoyuzhou": "xiaoyuzhou",
        "xueqiu": "xueqiu",
        "douyin": "douyin",
        "linkedin": "linkedin",
        "exa_search": "",
        "github": "",
        "youtube": "",
        "rss": "",
        "v2ex": "",
        "web": "",
    }
    
    def __init__(self):
        self.config = Config() if AGENT_REACH_AVAILABLE else None
        self.agent_reach_dir = AGENT_REACH_DIR
        
    def is_available(self) -> bool:
        """Check if Agent-Reach is available"""
        return AGENT_REACH_AVAILABLE and self.agent_reach_dir.exists()
    
    def get_channel_status(self) -> Dict[str, Any]:
        """Get status of all Agent-Reach channels"""
        if not self.is_available():
            return {
                "available": False,
                "error": "Agent-Reach not installed",
                "channels": {}
            }
        
        try:
            results = check_all(self.config)
            results = self._apply_saved_config_overlays(results)
            return {
                "available": True,
                "channels": {
                    name: {
                        "status": data["status"],
                        "message": data["message"],
                        "ready": data["status"] == "ok",
                        "tier": data.get("tier"),
                        "backends": data.get("backends", []),
                    }
                    for name, data in results.items()
                },
                "total_channels": len(results),
                "ready_channels": sum(1 for r in results.values() if r["status"] == "ok"),
                "warning_channels": sum(1 for r in results.values() if r["status"] == "warn"),
                "disabled_channels": sum(1 for r in results.values() if r["status"] == "off"),
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "channels": {}
            }

    def _apply_saved_config_overlays(self, results: Dict[str, dict]) -> Dict[str, dict]:
        """Reflect Agent-Reach config values that upstream doctor does not read itself."""
        if not self.config:
            return results
        enriched = {name: dict(data) for name, data in results.items()}
        twitter_auth = self.config.get("twitter_auth_token")
        twitter_ct0 = self.config.get("twitter_ct0")
        if twitter_auth and twitter_ct0 and "twitter" in enriched:
            probe = self._probe_twitter_with_config(str(twitter_auth), str(twitter_ct0))
            if probe["ok"]:
                enriched["twitter"]["status"] = "ok"
                enriched["twitter"]["message"] = "twitter-cli authenticated with saved Agent-Reach cookies"
            else:
                enriched["twitter"]["message"] = (
                    f"{enriched['twitter'].get('message', '')} Saved cookies are present; "
                    f"live auth check: {probe['message']}"
                ).strip()
        xueqiu_cookie = self.config.get("xueqiu_cookie")
        if xueqiu_cookie and "xueqiu" in enriched and enriched["xueqiu"].get("status") != "ok":
            enriched["xueqiu"]["message"] = (
                f"{enriched['xueqiu'].get('message', '')} Saved Xueqiu cookie is present."
            ).strip()
        github_token = self.config.get("github_token")
        if github_token and "github" in enriched:
            probe = self._probe_github_with_config(str(github_token))
            if probe["ok"]:
                enriched["github"]["status"] = "ok"
                enriched["github"]["message"] = "gh CLI authenticated with saved GH_TOKEN"
            else:
                enriched["github"]["message"] = (
                    f"{enriched['github'].get('message', '')} Saved GitHub token is present; "
                    f"live auth check: {probe['message']}"
                ).strip()
        return enriched

    def _probe_twitter_with_config(self, auth_token: str, ct0: str) -> Dict[str, Any]:
        from shutil import which

        twitter = which("twitter")
        if not twitter:
            return {"ok": False, "message": "twitter-cli is not installed"}
        env = os.environ.copy()
        env["TWITTER_AUTH_TOKEN"] = auth_token
        env["TWITTER_CT0"] = ct0
        try:
            result = subprocess.run(
                [twitter, "status"],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                env=env,
            )
        except Exception as exc:
            return {"ok": False, "message": str(exc)}
        output = (result.stdout or "") + (result.stderr or "")
        return {"ok": result.returncode == 0 and "ok: true" in output, "message": output[-300:] or "no output"}

    def _probe_github_with_config(self, token: str) -> Dict[str, Any]:
        from shutil import which

        gh = which("gh")
        if not gh:
            return {"ok": False, "message": "gh CLI is not installed"}
        env = os.environ.copy()
        env["GH_TOKEN"] = token
        try:
            result = subprocess.run(
                [gh, "auth", "status"],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                env=env,
            )
        except Exception as exc:
            return {"ok": False, "message": str(exc)}
        output = (result.stdout or "") + (result.stderr or "")
        return {"ok": result.returncode == 0, "message": output[-300:] or "no output"}

    def _credential_env(self) -> Dict[str, str]:
        if not self.config:
            return {}
        env: Dict[str, str] = {}
        github_token = self.config.get("github_token")
        if github_token:
            env["GH_TOKEN"] = str(github_token)
        twitter_auth = self.config.get("twitter_auth_token")
        twitter_ct0 = self.config.get("twitter_ct0")
        if twitter_auth and twitter_ct0:
            env["TWITTER_AUTH_TOKEN"] = str(twitter_auth)
            env["TWITTER_CT0"] = str(twitter_ct0)
        return env
    
    def get_channel_info(self, channel_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific channel"""
        status = self.get_channel_status()
        if channel_name in status.get("channels", {}):
            channel_data = status["channels"][channel_name]
            
            # Add additional info about what's needed
            installation_info = self._get_installation_info(channel_name)
            channel_data.update(installation_info)
            
            return channel_data
        return None
    
    def _get_installation_info(self, channel_name: str) -> Dict[str, Any]:
        """Get installation instructions for a channel"""
        installations = {
            "twitter": {
                "requires": ["twitter-cli"],
                "install_command": "python -m agent_reach.cli install --env=auto --channels=twitter",
                "config_needed": "cookie",
                "description": "Search tweets, read timelines, post tweets"
            },
            "reddit": {
                "requires": ["rdt-cli"],
                "install_command": "python -m agent_reach.cli install --env=auto --channels=reddit",
                "config_needed": "cookie",
                "description": "Search Reddit, read posts and comments"
            },
            "youtube": {
                "requires": ["yt-dlp"],
                "install_command": "python -m agent_reach.cli install --env=auto",
                "config_needed": "none",
                "description": "Extract video subtitles and metadata"
            },
            "xiaohongshu": {
                "requires": ["xhs-cli"],
                "install_command": "python -m agent_reach.cli install --env=auto --channels=xiaohongshu",
                "config_needed": "cookie",
                "description": "Search and read Xiaohongshu posts"
            },
            "bilibili": {
                "requires": ["yt-dlp"],
                "install_command": "python -m agent_reach.cli install --env=auto --channels=bilibili",
                "config_needed": "proxy (optional)",
                "description": "Extract Bilibili video content"
            },
            "linkedin": {
                "requires": ["mcporter", "linkedin-mcp-server"],
                "install_command": "python -m agent_reach.cli install --env=auto --channels=linkedin",
                "config_needed": "mcp_config",
                "description": "LinkedIn profile and company data"
            },
            "douyin": {
                "requires": ["mcporter", "douyin-mcp-server"],
                "install_command": "python -m agent_reach.cli install --env=auto --channels=douyin",
                "config_needed": "mcp_config",
                "description": "Parse Douyin video information"
            },
            "weibo": {
                "requires": ["mcporter", "mcp-server-weibo"],
                "install_command": "python -m agent_reach.cli install --env=auto --channels=weibo",
                "config_needed": "mcp_config",
                "description": "Weibo hot search and user data"
            },
            "web": {
                "requires": [],
                "install_command": "none",
                "config_needed": "none",
                "description": "Read any webpage via Jina Reader (always available)"
            },
            "github": {
                "requires": ["gh"],
                "install_command": "python -m agent_reach.cli install --env=auto",
                "config_needed": "optional (token for private repos)",
                "description": "Search repos, read issues, create PRs"
            },
            "exa_search": {
                "requires": ["mcporter"],
                "install_command": "python -m agent_reach.cli install --env=auto",
                "config_needed": "mcp_config",
                "description": "AI-powered web search"
            },
            "rss": {
                "requires": [],
                "install_command": "none",
                "config_needed": "none",
                "description": "Read RSS/Atom feeds (always available)"
            },
            "v2ex": {
                "requires": [],
                "install_command": "none",
                "config_needed": "none",
                "description": "V2EX community posts (always available)"
            },
            "xueqiu": {
                "requires": [],
                "install_command": "none",
                "config_needed": "cookie",
                "description": "Xueqiu stock data and discussions"
            },
            "wechat": {
                "requires": ["camoufox (optional)"],
                "install_command": "python -m agent_reach.cli install --env=auto --channels=wechat",
                "config_needed": "none",
                "description": "WeChat official account articles"
            },
            "xiaoyuzhou": {
                "requires": ["ffmpeg", "groq-api-key"],
                "install_command": "python -m agent_reach.cli install --env=auto --channels=xiaoyuzhou",
                "config_needed": "groq_key",
                "description": "Podcast transcription with Whisper"
            }
        }
        
        return installations.get(channel_name, {
            "requires": [],
            "install_command": "unknown",
            "config_needed": "unknown",
            "description": "No information available"
        })
    
    def install_channel(self, channel_name: str) -> Dict[str, Any]:
        """
        Install dependencies for a channel
        Returns status and message
        """
        if not self.is_available():
            return {"success": False, "message": "Agent-Reach not available"}
        
        info = self._get_installation_info(channel_name)
        install_channel = self.AGENT_REACH_INSTALL_CHANNELS.get(channel_name)
        if install_channel is None:
            return {"success": False, "message": f"Unknown channel: {channel_name}"}
        if info.get("install_command") in {"none", "unknown"}:
            return {
                "success": False,
                "message": f"No automatic installation available for {channel_name}",
                "manual_steps": info.get("description", "")
            }
        
        try:
            cmd = [sys.executable, "-m", "agent_reach.cli", "install", "--env=auto"]
            if install_channel:
                cmd.append(f"--channels={install_channel}")
            env = {
                **os.environ,
                "PYTHONPATH": f"{self.agent_reach_dir}{os.pathsep}{os.environ.get('PYTHONPATH', '')}",
                "AGENT_REACH_LANG": os.environ.get("AGENT_REACH_LANG", "en"),
            }
            result = subprocess.run(
                cmd,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
                cwd=str(self.agent_reach_dir),
                env=env,
            )
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "message": f"Successfully installed {channel_name}",
                    "output": result.stdout[-4000:],
                    "command": " ".join(cmd),
                }
            else:
                return {
                    "success": False,
                    "message": f"Installation failed: {(result.stderr or result.stdout)[-1000:]}",
                    "command": " ".join(cmd)
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": "Installation timed out (>5 minutes)"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Installation error: {str(e)}"
            }
    
    def configure_channel(self, channel_name: str, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Configure a channel with provided data (cookies, tokens, etc.)
        """
        if not self.is_available():
            return {"success": False, "message": "Agent-Reach not available"}
        
        try:
            # Store configuration in Agent-Reach config
            if channel_name == "twitter" and "cookie" in config_data:
                parsed = self._parse_twitter_cookie(config_data["cookie"])
                if not parsed:
                    return {
                        "success": False,
                        "message": "Twitter cookie must include auth_token and ct0"
                    }
                auth_token, ct0 = parsed
                self.config.set("twitter_auth_token", auth_token)
                self.config.set("twitter_ct0", ct0)
            elif channel_name == "reddit" and "cookie" in config_data:
                self.config.set("reddit_cookies", config_data["cookie"])
            elif channel_name == "github" and "token" in config_data:
                self.config.set("github_token", config_data["token"])
            elif channel_name == "xiaohongshu" and "cookie" in config_data:
                self.config.set("xhs_cookies", config_data["cookie"])
            elif channel_name == "bilibili" and "proxy" in config_data:
                self.config.set("bilibili_proxy", config_data["proxy"])
            elif channel_name == "xiaoyuzhou" and "groq_key" in config_data:
                self.config.set("groq_api_key", config_data["groq_key"])
            elif channel_name == "xueqiu" and "cookie" in config_data:
                self.config.set("xueqiu_cookie", config_data["cookie"])
            else:
                return {
                    "success": False,
                    "message": f"Unknown configuration type for {channel_name}"
                }
            
            return {
                "success": True,
                "message": f"Configuration saved for {channel_name}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Configuration error: {str(e)}"
            }

    def _parse_twitter_cookie(self, value: str) -> tuple[str, str] | None:
        auth_token = ""
        ct0 = ""
        if "auth_token=" in value and "ct0=" in value:
            for part in value.replace(";", " ").split():
                if part.startswith("auth_token="):
                    auth_token = part.split("=", 1)[1]
                elif part.startswith("ct0="):
                    ct0 = part.split("=", 1)[1]
        elif len(value.split()) == 2 and "=" not in value:
            auth_token, ct0 = value.split()
        if auth_token and ct0:
            return auth_token, ct0
        return None
    
    def test_channel(self, channel_name: str) -> Dict[str, Any]:
        """
        Test if a channel is working
        """
        if not self.is_available():
            return {"success": False, "message": "Agent-Reach not available"}
        
        try:
            # Get fresh status
            status = self.get_channel_status()
            
            if channel_name not in status.get("channels", {}):
                return {"success": False, "message": f"Unknown channel: {channel_name}"}
            
            channel_data = status["channels"][channel_name]
            
            return {
                "success": channel_data["ready"],
                "status": channel_data["status"],
                "message": channel_data["message"],
                "ready": channel_data["ready"]
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Test error: {str(e)}"
            }
    
    def get_all_channels(self) -> List[Dict[str, Any]]:
        """Get list of all channels with their info"""
        status = self.get_channel_status()
        channels = []
        
        for name in self.CHANNEL_NAMES:
            channel_info = self._get_installation_info(name)
            channel_status = status.get("channels", {}).get(name, {})
            
            channels.append({
                "name": name,
                "display_name": name.replace("_", " ").title(),
                "status": channel_status.get("status", "unknown"),
                "ready": channel_status.get("ready", False),
                "message": channel_status.get("message", ""),
                "description": channel_info.get("description", ""),
                "requires": channel_info.get("requires", []),
                "config_needed": channel_info.get("config_needed", "none"),
                "install_command": channel_info.get("install_command", "none")
            })
        
        return channels

    async def run_scrape(
        self,
        query: str,
        location: str = "",
        limit: int = 25,
        channels: List[str] | None = None,
        real_run: bool = True,
        job_id: str | None = None,
    ) -> Dict[str, Any]:
        """Start the real ASAGUS Agent-Reach adapter as a background run."""
        if not self.is_available():
            return {"success": False, "message": "Agent-Reach not available"}

        from asagus.services.tools_runner import run_tool

        safe_limit = min(max(int(limit or 25), 1), 5000)
        selected_channels = [name for name in (channels or []) if name in self.CHANNEL_NAMES]
        run_job_id = job_id or f"agent-reach-manual-{int(time.time())}"
        env = {
            "ASAGUS_JOB_ID": run_job_id,
            "ASAGUS_QUERY": query,
            "ASAGUS_LOCATION": location,
            "ASAGUS_LIMIT": str(safe_limit),
            "ASAGUS_MODE": "max",
            "ASAGUS_RUNS_ROOT": str(RUNS_ROOT),
            "ASAGUS_TOOL_REAL_RUN": "1" if real_run else "0",
            "ASAGUS_DRY_RUN": "0" if real_run else "1",
            "ASAGUS_TOOL_MAX_RESULTS": str(min(max(safe_limit, 5), 50)),
            "ASAGUS_AGENT_REACH_CHANNELS": ",".join(selected_channels),
            **self._credential_env(),
        }
        args = ["--mode", "max", "--query", query, "--location", location, "--limit", str(min(max(safe_limit, 5), 50))]
        result = await run_tool("agent-reach", args=args, env_extra=env)
        return {
            "success": True,
            "message": "Agent-Reach adapter started",
            "query": query,
            "location": location,
            "limit": safe_limit,
            "job_id": run_job_id,
            "channels_requested": selected_channels,
            **result,
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get usage statistics for Agent-Reach"""
        status = self.get_channel_status()
        
        return {
            "total_channels": status.get("total_channels", 0),
            "ready_channels": status.get("ready_channels", 0),
            "warning_channels": status.get("warning_channels", 0),
            "disabled_channels": status.get("disabled_channels", 0),
            "availability_percentage": (
                (status.get("ready_channels", 0) / status.get("total_channels", 1)) * 100
                if status.get("total_channels", 0) > 0 else 0
            )
        }


# Singleton instance
_service_instance: Optional[AgentReachService] = None


def get_agent_reach_service() -> AgentReachService:
    """Get or create the Agent-Reach service singleton"""
    global _service_instance
    if _service_instance is None:
        _service_instance = AgentReachService()
    return _service_instance
