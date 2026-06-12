"""
ASAGUS Adapter for Scrapling
Uses Scrapling library for adaptive scraping with the unified pipeline.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from unified_tool_adapter import UnifiedToolAdapter


class ScraplingAdapter(UnifiedToolAdapter):
    """Adapter for Scrapling tool."""
    
    def run(self):
        """Run Scrapling with ASAGUS job context."""
        context = self.get_job_context()
        
        try:
            # Check if scrapling is available
            import scrapling
            
            if not self.real_run:
                sample_data = {
                    "tool_id": self.tool_id,
                    "status": "ready",
                    "message": "Scrapling is available and ready",
                    "scrapling_version": scrapling.__version__ if hasattr(scrapling, '__version__') else "unknown",
                    "job_context": context,
                }
                self.save_metadata_json(sample_data)
                return sample_data
            
            # For real run, Scrapling is used by main scraper, not standalone
            metadata = {
                "tool_id": self.tool_id,
                "status": "integrated",
                "message": "Scrapling is integrated into main ASAGUS extraction layer",
                "note": "This tool provides parser capabilities to the main scraper",
                "job_context": context,
            }
            self.save_metadata_json(metadata)
            return metadata
            
        except ImportError:
            error_data = {
                "tool_id": self.tool_id,
                "status": "not_installed",
                "error": "Scrapling package not found",
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
    adapter = ScraplingAdapter()
    result = adapter.run()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
