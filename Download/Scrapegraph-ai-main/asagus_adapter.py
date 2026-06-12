"""
ASAGUS Adapter for ScrapeGraph AI
Uses LLM-powered extraction with the unified pipeline.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from unified_tool_adapter import UnifiedToolAdapter, get_llm_config


class ScrapeGraphAIAdapter(UnifiedToolAdapter):
    """Adapter for ScrapeGraph AI tool."""
    
    def run(self):
        """Run ScrapeGraph AI with ASAGUS job context."""
        context = self.get_job_context()
        llm_config = get_llm_config()
        
        try:
            # Check if scrapegraphai is available
            import scrapegraphai
            
            if not self.real_run or llm_config["provider"] == "disabled":
                sample_data = {
                    "tool_id": self.tool_id,
                    "status": "needs_llm" if llm_config["provider"] == "disabled" else "ready",
                    "message": "LLM configuration required for ScrapeGraph AI" if llm_config["provider"] == "disabled" else "ScrapeGraph AI ready",
                    "llm_provider": llm_config["provider"],
                    "job_context": context,
                }
                self.save_metadata_json(sample_data)
                return sample_data
            
            # For real run with LLM configured
            metadata = {
                "tool_id": self.tool_id,
                "status": "integrated",
                "message": "ScrapeGraph AI provides LLM extraction to main scraper",
                "llm_provider": llm_config["provider"],
                "note": "This tool's LLM capabilities are used in the main ASAGUS extraction cascade",
                "job_context": context,
            }
            self.save_metadata_json(metadata)
            return metadata
            
        except ImportError:
            error_data = {
                "tool_id": self.tool_id,
                "status": "not_installed",
                "error": "ScrapeGraphAI package not found",
                "install_command": "pip install scrapegraphai",
                "job_context": context,
            }
            self.save_metadata_json(error_data)
            return error_data
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
    adapter = ScrapeGraphAIAdapter()
    result = adapter.run()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
