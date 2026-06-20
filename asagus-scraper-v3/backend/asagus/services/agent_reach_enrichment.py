"""
Agent-Reach Enrichment Service - Phase 4 Integration
Enriches ASAGUS business records using Agent-Reach channels in MAX mode
"""
from __future__ import annotations

import sys
import os
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
import re

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


class AgentReachEnrichmentService:
    """
    Service for enriching business records using Agent-Reach multi-channel scraping
    
    Integrates with ASAGUS MAX mode to provide additional data enrichment from:
    - Web scraping (Jina Reader)
    - Social media (Twitter, LinkedIn)
    - Developer platforms (GitHub)
    - Content platforms (YouTube, RSS)
    """
    
    def __init__(self):
        self.agent_reach_dir = AGENT_REACH_DIR
        self.config = Config() if AGENT_REACH_AVAILABLE else None
        self.enabled_channels: List[str] = []
        
        if AGENT_REACH_AVAILABLE:
            self._detect_available_channels()
    
    def is_available(self) -> bool:
        """Check if Agent-Reach is installed and available"""
        return AGENT_REACH_AVAILABLE and self.agent_reach_dir.exists()
    
    def _detect_available_channels(self):
        """Detect which Agent-Reach channels are ready to use"""
        if not self.is_available():
            return
        
        try:
            results = check_all(self.config)
            self.enabled_channels = [
                name for name, data in results.items()
                if data.get("status") == "ok"
            ]
        except Exception:
            self.enabled_channels = []
    
    async def ensure_installed(self) -> Dict[str, Any]:
        """
        Ensure Agent-Reach is installed, install if missing
        Returns installation status
        """
        if self.is_available():
            return {
                "installed": True,
                "message": "Agent-Reach already installed",
                "channels": self.enabled_channels
            }
        
        # Try to install Agent-Reach
        try:
            # Check if pip is available
            result = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pip", "install",
                str(self.agent_reach_dir) if self.agent_reach_dir.exists() else "git+https://github.com/Panniantong/agent-reach.git@main",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=300)
            
            if result.returncode == 0:
                # Installation successful, try importing again
                global AGENT_REACH_AVAILABLE
                try:
                    from agent_reach.config import Config
                    from agent_reach.doctor import check_all
                    AGENT_REACH_AVAILABLE = True
                    self.config = Config()
                    self._detect_available_channels()
                    
                    return {
                        "installed": True,
                        "message": "Agent-Reach installed successfully",
                        "channels": self.enabled_channels,
                        "output": stdout.decode() if stdout else ""
                    }
                except ImportError as e:
                    return {
                        "installed": False,
                        "message": f"Installation succeeded but import failed: {e}",
                        "fallback_available": True
                    }
            else:
                return {
                    "installed": False,
                    "message": f"Installation failed: {stderr.decode() if stderr else 'Unknown error'}",
                    "fallback_available": True
                }
        except asyncio.TimeoutError:
            return {
                "installed": False,
                "message": "Installation timed out after 5 minutes",
                "fallback_available": True
            }
        except Exception as e:
            return {
                "installed": False,
                "message": f"Installation error: {str(e)}",
                "fallback_available": True
            }
    
    async def enrich_website_content(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Use Agent-Reach web channel (Jina Reader) to scrape website content
        """
        if not self.is_available() or "web" not in self.enabled_channels:
            return None
        
        try:
            # Use Jina Reader API directly (no auth required)
            result = await asyncio.create_subprocess_exec(
                "curl", "-s", f"https://r.jina.ai/{url}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=30)
            
            if result.returncode == 0 and stdout:
                content = stdout.decode('utf-8', errors='ignore')
                return {
                    "success": True,
                    "content": content[:5000],  # Limit to first 5000 chars
                    "content_length": len(content),
                    "channel": "web",
                    "source": "jina_reader"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "channel": "web"
            }
        
        return None
    
    def _extract_email_from_text(self, text: str) -> List[str]:
        """Extract email addresses from text using regex"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return list(set(re.findall(email_pattern, text)))
    
    def _extract_phone_from_text(self, text: str) -> List[str]:
        """Extract phone numbers from text using regex"""
        # International format, various patterns
        phone_patterns = [
            r'\+\d{1,4}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',  # +1-234-567-8900
            r'\(\d{3}\)[-.\s]?\d{3}[-.\s]?\d{4}',  # (123) 456-7890
            r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # 123-456-7890
        ]
        
        phones = []
        for pattern in phone_patterns:
            phones.extend(re.findall(pattern, text))
        
        return list(set(phones))[:5]  # Limit to 5 phone numbers
    
    async def enrich_business_record(
        self,
        record: Dict[str, Any],
        enable_web_scraping: bool = True,
        enable_social_search: bool = False
    ) -> Dict[str, Any]:
        """
        Enrich a single business record using Agent-Reach channels
        
        Args:
            record: Business record from primary scraper
            enable_web_scraping: Whether to scrape business website
            enable_social_search: Whether to search social platforms (requires auth)
        
        Returns:
            Enriched record with additional fields
        """
        enriched = record.copy()
        enriched["agent_reach_enriched"] = False
        enriched["agent_reach_channels_used"] = []
        enriched["agent_reach_data"] = {}
        
        if not self.is_available():
            enriched["agent_reach_status"] = "not_available"
            return enriched
        
        # Enrich from website content
        website_url = record.get("website_url") or record.get("website") or record.get("url")
        if website_url and enable_web_scraping and "web" in self.enabled_channels:
            web_data = await self.enrich_website_content(website_url)
            
            if web_data and web_data.get("success"):
                content = web_data.get("content", "")
                
                # Extract emails if not present
                if not record.get("email"):
                    emails = self._extract_email_from_text(content)
                    if emails:
                        enriched["email"] = emails[0]
                        enriched["agent_reach_data"]["found_emails"] = emails
                        enriched["agent_reach_enriched"] = True
                
                # Extract phones if not present
                if not record.get("phone") and not record.get("whatsapp"):
                    phones = self._extract_phone_from_text(content)
                    if phones:
                        enriched["phone"] = phones[0]
                        enriched["agent_reach_data"]["found_phones"] = phones
                        enriched["agent_reach_enriched"] = True
                
                # Store website metadata
                enriched["agent_reach_data"]["website_scraped"] = True
                enriched["agent_reach_data"]["content_length"] = web_data.get("content_length", 0)
                enriched["agent_reach_channels_used"].append("web")
        
        # Future: Social media enrichment (Twitter, LinkedIn)
        if enable_social_search:
            # Check if Twitter is available
            if "twitter" in self.enabled_channels:
                # Search Twitter for business mentions
                # enriched = await self._enrich_from_twitter(enriched)
                pass
            
            # Check if GitHub is available (for tech companies)
            if "github" in self.enabled_channels:
                # Search GitHub for company repos
                # enriched = await self._enrich_from_github(enriched)
                pass
        
        if enriched["agent_reach_channels_used"]:
            enriched["agent_reach_status"] = "enriched"
        else:
            enriched["agent_reach_status"] = "no_enrichment"
        
        return enriched
    
    async def enrich_batch(
        self,
        records: List[Dict[str, Any]],
        enable_web_scraping: bool = True,
        enable_social_search: bool = False,
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Enrich multiple business records concurrently
        
        Args:
            records: List of business records
            enable_web_scraping: Whether to scrape websites
            enable_social_search: Whether to search social platforms
            max_concurrent: Maximum concurrent enrichments
        
        Returns:
            List of enriched records
        """
        if not self.is_available():
            return records
        
        # Create semaphore for concurrent control
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def enrich_with_semaphore(record: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                return await self.enrich_business_record(
                    record,
                    enable_web_scraping=enable_web_scraping,
                    enable_social_search=enable_social_search
                )
        
        # Enrich all records concurrently
        tasks = [enrich_with_semaphore(record) for record in records]
        enriched_records = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and return successful enrichments
        result = []
        for i, enriched in enumerate(enriched_records):
            if isinstance(enriched, Exception):
                # If enrichment failed, return original record
                result.append(records[i])
            else:
                result.append(enriched)
        
        return result
    
    def get_enrichment_stats(self, enriched_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate enrichment statistics
        """
        total = len(enriched_records)
        enriched_count = sum(1 for r in enriched_records if r.get("agent_reach_enriched", False))
        
        channels_used = {}
        for record in enriched_records:
            for channel in record.get("agent_reach_channels_used", []):
                channels_used[channel] = channels_used.get(channel, 0) + 1
        
        emails_found = sum(
            1 for r in enriched_records 
            if r.get("agent_reach_data", {}).get("found_emails")
        )
        
        phones_found = sum(
            1 for r in enriched_records 
            if r.get("agent_reach_data", {}).get("found_phones")
        )
        
        return {
            "total_records": total,
            "enriched_records": enriched_count,
            "enrichment_rate": (enriched_count / total * 100) if total > 0 else 0,
            "channels_used": channels_used,
            "emails_found": emails_found,
            "phones_found": phones_found,
            "available_channels": self.enabled_channels,
        }


# Singleton instance
_enrichment_service: Optional[AgentReachEnrichmentService] = None


def get_enrichment_service() -> AgentReachEnrichmentService:
    """Get or create the Agent-Reach enrichment service singleton"""
    global _enrichment_service
    if _enrichment_service is None:
        _enrichment_service = AgentReachEnrichmentService()
    return _enrichment_service
