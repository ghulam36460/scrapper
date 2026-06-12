"""
ASAGUS Adapter for Agent Reach
AI-powered outreach agent integration.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from unified_tool_adapter import UnifiedToolAdapter, get_llm_config


class AgentReachAdapter(UnifiedToolAdapter):
    """Adapter for Agent Reach tool."""
    
    def run(self):
        """Run Agent Reach with ASAGUS job context."""
        context = self.get_job_context()
        llm_config = get_llm_config()
        
        try:
            # Check for agent_reach package
            try:
                import agent_reach
                agent_reach_available = True
            except ImportError:
                agent_reach_available = False
            
            if not self.real_run or llm_config["provider"] == "disabled":
                sample_data = {
                    "tool_id": self.tool_id,
                    "status": "needs_llm" if llm_config["provider"] == "disabled" else "ready",
                    "message": "LLM configuration required" if llm_config["provider"] == "disabled" else "Agent Reach ready",
                    "agent_reach_available": agent_reach_available,
                    "llm_provider": llm_config["provider"],
                    "job_context": context,
                }
                self.save_metadata_json(sample_data)
                return sample_data
            
            # Agent Reach is an outreach tool, not a scraper
            metadata = {
                "tool_id": self.tool_id,
                "status": "ready",
                "message": "Agent Reach provides AI-powered outreach capabilities",
                "llm_provider": llm_config["provider"],
                "note": "This tool is for outreach automation, not scraping",
                "job_context": context,
            }
            self.save_metadata_json(metadata)
            return metadata
            
        except Exception as e:
            error_data = {
                "tool_id": self.tool_id,
                "status": "error",
                "error": str(e),
                "job_context": context,
            }
            self.save_metadata_json(error_data)
            return error_data


def main():
    import json
    adapter = AgentReachAdapter()
    result = adapter.run()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
