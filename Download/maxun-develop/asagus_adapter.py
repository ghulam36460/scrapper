"""
ASAGUS Adapter for Maxun
Visual scraper integration (Node.js project).
"""
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from unified_tool_adapter import UnifiedToolAdapter


class MaxunAdapter(UnifiedToolAdapter):
    """Adapter for Maxun visual scraper."""
    
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
    
    def run(self):
        """Run Maxun with ASAGUS job context."""
        context = self.get_job_context()
        
        try:
            node_available = self.check_node_available()
            
            if not node_available:
                error_data = {
                    "tool_id": self.tool_id,
                    "status": "node_not_found",
                    "message": "Node.js is required for Maxun but not found",
                    "install_instructions": "Install Node.js from https://nodejs.org/",
                    "job_context": context,
                }
                self.save_metadata_json(error_data)
                return error_data
            
            if not self.real_run:
                sample_data = {
                    "tool_id": self.tool_id,
                    "status": "ready",
                    "message": "Maxun is ready (Node.js found)",
                    "note": "Maxun is a visual scraper - requires UI interaction",
                    "node_available": True,
                    "job_context": context,
                }
                self.save_metadata_json(sample_data)
                return sample_data
            
            # Maxun is a visual scraper with UI - not suitable for batch automation
            metadata = {
                "tool_id": self.tool_id,
                "status": "manual_tool",
                "message": "Maxun is a visual scraper requiring manual interaction",
                "note": "This tool is designed for creating scraping workflows visually",
                "node_available": True,
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
    adapter = MaxunAdapter()
    result = adapter.run()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
