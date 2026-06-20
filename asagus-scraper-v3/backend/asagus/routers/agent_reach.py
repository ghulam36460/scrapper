"""
Agent-Reach Router — API endpoints for Agent-Reach integration and configuration
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from asagus.services.agent_reach_service import get_agent_reach_service, AgentReachService
from asagus.routers.deps import require_operator

router = APIRouter(prefix="/api/agent-reach", tags=["agent-reach"])


# ─── Request Models ─────────────────────────────────────────────────────


class ChannelConfigRequest(BaseModel):
    """Request model for configuring a channel"""
    cookie: str | None = Field(None, description="Cookie string for authentication")
    token: str | None = Field(None, description="API token or access token")
    proxy: str | None = Field(None, description="Proxy URL")
    groq_key: str | None = Field(None, description="Groq API key for transcription")
    mcp_config: Dict[str, Any] | None = Field(None, description="MCP server configuration")


# ─── Endpoints ──────────────────────────────────────────────────────────


@router.get("/health", dependencies=[Depends(require_operator)])
async def health_check(service: AgentReachService = Depends(get_agent_reach_service)) -> Dict[str, Any]:
    """Check if Agent-Reach is available and accessible"""
    return {
        "available": service.is_available(),
        "agent_reach_dir": str(service.agent_reach_dir),
        "status": "ready" if service.is_available() else "unavailable"
    }


@router.get("/status", dependencies=[Depends(require_operator)])
async def get_status(service: AgentReachService = Depends(get_agent_reach_service)) -> Dict[str, Any]:
    """
    Get comprehensive status of all Agent-Reach channels
    
    Returns:
        - available: Whether Agent-Reach is installed and accessible
        - channels: Dictionary of channel statuses with ready/warning/disabled states
        - total_channels: Total number of channels
        - ready_channels: Number of channels ready to use
        - warning_channels: Number of channels with warnings (partially working)
        - disabled_channels: Number of disabled channels
    """
    if not service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Agent-Reach is not available. Please check installation."
        )
    
    return service.get_channel_status()


@router.get("/channels", dependencies=[Depends(require_operator)])
async def list_channels(service: AgentReachService = Depends(get_agent_reach_service)) -> Dict[str, Any]:
    """
    List all available Agent-Reach channels with their details
    
    Returns:
        - channels: List of all channels with name, status, requirements, and descriptions
    """
    if not service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Agent-Reach is not available. Please check installation."
        )
    
    channels = service.get_all_channels()
    return {
        "count": len(channels),
        "channels": channels
    }


@router.get("/channels/{channel_name}", dependencies=[Depends(require_operator)])
async def get_channel_info(
    channel_name: str,
    service: AgentReachService = Depends(get_agent_reach_service)
) -> Dict[str, Any]:
    """
    Get detailed information about a specific channel
    
    Args:
        channel_name: Name of the channel (e.g., 'twitter', 'github', 'web')
    
    Returns:
        - Channel status, requirements, installation instructions, and configuration needs
    
    Raises:
        404: If channel is not found
    """
    if not service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Agent-Reach is not available. Please check installation."
        )
    
    channel_info = service.get_channel_info(channel_name)
    
    if not channel_info:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_name}' not found"
        )
    
    return channel_info


@router.post("/channels/{channel_name}/install", dependencies=[Depends(require_operator)])
async def install_channel(
    channel_name: str,
    service: AgentReachService = Depends(get_agent_reach_service)
) -> Dict[str, Any]:
    """
    Install dependencies for a specific channel
    
    Args:
        channel_name: Name of the channel to install
    
    Returns:
        - success: Whether installation succeeded
        - message: Installation status message
        - output: Installation command output (if available)
    
    Note:
        Some channels cannot be installed automatically and require manual setup.
        Check the 'manual_steps' field in the response for instructions.
    """
    if not service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Agent-Reach is not available. Please check installation."
        )
    
    result = service.install_channel(channel_name)
    
    if not result["success"]:
        # Return 200 with success=false for manual installation requirements
        # Return 500 only for actual errors
        if "manual_steps" in result or "No automatic installation" in result.get("message", ""):
            return result
        raise HTTPException(
            status_code=500,
            detail=result["message"]
        )
    
    return result


@router.post("/channels/{channel_name}/configure", dependencies=[Depends(require_operator)])
async def configure_channel(
    channel_name: str,
    config: ChannelConfigRequest,
    service: AgentReachService = Depends(get_agent_reach_service)
) -> Dict[str, Any]:
    """
    Configure a channel with authentication credentials or settings
    
    Args:
        channel_name: Name of the channel to configure
        config: Configuration data (cookies, tokens, proxy, etc.)
    
    Returns:
        - success: Whether configuration was saved successfully
        - message: Configuration status message
    
    Examples:
        - Twitter: {"cookie": "auth_token=..."}
        - GitHub: {"token": "ghp_..."}
        - Bilibili: {"proxy": "http://proxy:8080"}
        - Xiaoyuzhou: {"groq_key": "gsk_..."}
    """
    if not service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Agent-Reach is not available. Please check installation."
        )
    
    # Convert Pydantic model to dict, filtering out None values
    config_data = {k: v for k, v in config.model_dump().items() if v is not None}
    
    if not config_data:
        raise HTTPException(
            status_code=400,
            detail="No configuration data provided. Please provide at least one of: cookie, token, proxy, groq_key, mcp_config"
        )
    
    result = service.configure_channel(channel_name, config_data)
    
    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result["message"]
        )
    
    return result


@router.post("/channels/{channel_name}/test", dependencies=[Depends(require_operator)])
async def test_channel(
    channel_name: str,
    service: AgentReachService = Depends(get_agent_reach_service)
) -> Dict[str, Any]:
    """
    Test if a channel is working correctly
    
    Args:
        channel_name: Name of the channel to test
    
    Returns:
        - success: Whether the channel test passed
        - status: Channel status (ok, warn, off)
        - message: Test result message
        - ready: Whether channel is ready to use
    """
    if not service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Agent-Reach is not available. Please check installation."
        )
    
    result = service.test_channel(channel_name)
    
    return result


@router.get("/statistics", dependencies=[Depends(require_operator)])
async def get_statistics(service: AgentReachService = Depends(get_agent_reach_service)) -> Dict[str, Any]:
    """
    Get Agent-Reach usage statistics and availability metrics
    
    Returns:
        - total_channels: Total number of channels
        - ready_channels: Number of ready channels
        - warning_channels: Number of channels with warnings
        - disabled_channels: Number of disabled channels
        - availability_percentage: Percentage of channels that are ready
    """
    if not service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Agent-Reach is not available. Please check installation."
        )
    
    return service.get_statistics()


@router.post("/run-scrape", dependencies=[Depends(require_operator)])
async def run_agent_reach_scrape(
    query: str = Query(..., min_length=2, max_length=300),
    location: str = Query("", max_length=160),
    limit: int = Query(25, ge=1, le=5000),
    channels: str | None = Query(None),
    real_run: bool = Query(True),
    service: AgentReachService = Depends(get_agent_reach_service)
) -> Dict[str, Any]:
    """
    Trigger an Agent-Reach scraping job
    
    Args:
        query: Search query or target to scrape
        channels: List of specific channels to use (optional, uses all ready channels if not specified)
    
    Returns:
        - job_id: Identifier for the scraping job
        - status: Job status
        - channels_used: List of channels that will be used
    
    This launches the same production adapter that ASAGUS MAX mode uses and
    writes real CSV/JSON artifacts into Download/.asagus-runs/<job-id>/.
    """
    if not service.is_available():
        raise HTTPException(
            status_code=503,
            detail="Agent-Reach is not available. Please check installation."
        )
    
    status = service.get_channel_status()
    ready_channels = [
        name for name, data in status.get("channels", {}).items()
        if data.get("ready", False)
    ]

    requested_channels = [
        item.strip()
        for item in (channels or "").split(",")
        if item.strip()
    ]
    if requested_channels:
        # Filter to only requested channels that are ready
        channels_to_use = [ch for ch in requested_channels if ch in ready_channels]
    else:
        # Let the native Agent Reach co-engine select all ready channels after
        # dependency bootstrap, so newly installed venv tools are not excluded.
        channels_to_use = None
    
    if requested_channels and not channels_to_use:
        raise HTTPException(
            status_code=400,
            detail="No ready channels available for scraping. Please configure and install channels first."
        )
    
    return await service.run_scrape(
        query=query,
        location=location,
        limit=limit,
        channels=channels_to_use,
        real_run=real_run,
    )


@router.get("/enrichment-stats/{job_id}", dependencies=[Depends(require_operator)])
async def get_enrichment_stats(
    job_id: str,
) -> Dict[str, Any]:
    """
    Get Agent-Reach enrichment statistics for a completed job
    
    Args:
        job_id: The ASAGUS job ID
    
    Returns:
        - total_records: Total records in the job
        - enriched_records: Number of records enriched by Agent-Reach
        - enrichment_rate: Percentage of records enriched
        - channels_used: Dictionary of channels and usage counts
        - emails_found: Number of emails found by Agent-Reach
        - phones_found: Number of phones found by Agent-Reach
    
    Note:
        This endpoint shows how many records were enhanced by Agent-Reach
        during MAX mode execution.
    """
    from asagus.services.runtime import runtime
    from asagus.services.agent_reach_enrichment import get_enrichment_service
    
    agent_reach = get_enrichment_service()
    
    if not agent_reach.is_available():
        raise HTTPException(
            status_code=503,
            detail="Agent-Reach is not available."
        )
    
    # Get all records from the job
    try:
        all_records = await runtime.list_records()
        
        # Filter records from this specific job if possible
        # (For now, return stats for all records as job filtering isn't implemented)
        enriched_records = [
            r.model_dump() for r in all_records 
            if r.raw_fields.get("agent_reach_data")
        ]
        
        stats = agent_reach.get_enrichment_stats(enriched_records if enriched_records else all_records)
        stats["job_id"] = job_id
        
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get enrichment stats: {str(e)}"
        )
