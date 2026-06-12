"""
ASAGUS Adapter for WhatsApp Number Detector
WhatsApp validation service integration (Node.js project).
"""
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from unified_tool_adapter import UnifiedToolAdapter


class WhatsAppDetectorAdapter(UnifiedToolAdapter):
    """Adapter for WhatsApp number detector."""
    
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
        """Run WhatsApp detector with ASAGUS job context."""
        context = self.get_job_context()
        
        try:
            node_available = self.check_node_available()
            
            if not node_available:
                error_data = {
                    "tool_id": self.tool_id,
                    "status": "node_not_found",
                    "message": "Node.js is required but not found",
                    "install_instructions": "Install Node.js from https://nodejs.org/",
                    "job_context": context,
                }
                self.save_metadata_json(error_data)
                return error_data
            
            # WhatsApp detector is a post-processing tool
            metadata = {
                "tool_id": self.tool_id,
                "status": "ready",
                "message": "WhatsApp detector provides wa.me link validation",
                "note": "This tool validates WhatsApp numbers after they are extracted",
                "node_available": True,
                "integration": "Main ASAGUS enrichment layer generates wa.me links automatically",
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
    adapter = WhatsAppDetectorAdapter()
    result = adapter.run()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
