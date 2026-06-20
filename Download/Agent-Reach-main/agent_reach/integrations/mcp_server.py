# -*- coding: utf-8 -*-
"""
Agent Reach MCP Server — expose doctor/status as MCP tool.

Run: python -m agent_reach.integrations.mcp_server

Agent Reach is an installer + doctor tool. For actual reading/searching,
agents should call upstream tools directly (twitter-cli, yt-dlp, mcporter, etc.).
"""

import asyncio
import json
import sys

from agent_reach.config import Config
from agent_reach.core import AgentReach

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    HAS_MCP = True
except ImportError:
    HAS_MCP = False


def create_server():
    if not HAS_MCP:
        print("MCP not installed. Install: pip install agent-reach[mcp]", file=sys.stderr)
        sys.exit(1)

    server = Server("agent-reach")
    config = Config()
    eyes = AgentReach(config)

    @server.list_tools()
    async def list_tools():
        return [
            Tool(name="get_status",
                 description="Get Agent Reach status: which channels are installed and active.",
                 inputSchema={"type": "object", "properties": {}}),
            Tool(name="get_asagus_status",
                 description="Get ASAGUS co-engine readiness, backend venv dependency status, and ready channels.",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "bootstrap": {"type": "boolean", "default": True},
                     },
                 }),
            Tool(name="run_asagus_job",
                 description="Run Agent Reach as an ASAGUS co-engine job. Dry-run unless real_run is true.",
                 inputSchema={
                     "type": "object",
                     "properties": {
                         "query": {"type": "string"},
                         "location": {"type": "string"},
                         "limit": {"type": "integer", "default": 25},
                         "job_id": {"type": "string"},
                         "channels": {"type": "string"},
                         "real_run": {"type": "boolean", "default": False},
                     },
                     "required": ["query"],
                 }),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        try:
            if name == "get_status":
                result = eyes.doctor_report()
            elif name == "get_asagus_status":
                from agent_reach.integrations.asagus import AsagusCoEngine, AsagusJobContext

                bootstrap = bool(arguments.get("bootstrap", True)) if arguments else True
                result = AsagusCoEngine(
                    AsagusJobContext.from_env(),
                    bootstrap_dependencies=bootstrap,
                ).status()
            elif name == "run_asagus_job":
                from agent_reach.integrations.asagus import AsagusCoEngine, AsagusJobContext

                arguments = arguments or {}
                context = AsagusJobContext.from_env()
                context.query = str(arguments.get("query") or context.query)
                context.location = str(arguments.get("location") or context.location)
                context.limit = int(arguments.get("limit") or context.limit)
                context.job_id = str(arguments.get("job_id") or context.job_id)
                context.real_run = bool(arguments.get("real_run", False))
                channels = str(arguments.get("channels") or "")
                context.requested_channels = [item.strip() for item in channels.split(",") if item.strip()]
                context.output_dir = context.runs_root / context.job_id
                result = AsagusCoEngine(context).run()
            else:
                result = f"Unknown tool: {name}"

            text = json.dumps(result, ensure_ascii=False, indent=2) if isinstance(result, (dict, list)) else str(result)
            return [TextContent(type="text", text=text)]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    return server


async def main():
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
