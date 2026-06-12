"""
ASAGUS Adapter for Scrapy
Integrates Scrapy framework with the unified pipeline.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from unified_tool_adapter import UnifiedToolAdapter


class ScrapyAdapter(UnifiedToolAdapter):
    """Adapter for Scrapy framework."""
    
    def run(self):
        """Run Scrapy with ASAGUS job context."""
        context = self.get_job_context()
        
        try:
            import scrapy
            
            if not self.real_run:
                sample_data = {
                    "tool_id": self.tool_id,
                    "status": "ready",
                    "message": "Scrapy framework is available",
                    "scrapy_version": scrapy.__version__,
                    "job_context": context,
                }
                self.save_metadata_json(sample_data)
                return sample_data
            
            # Scrapy is used as framework, not standalone scraper
            metadata = {
                "tool_id": self.tool_id,
                "status": "integrated",
                "message": "Scrapy framework available for custom spiders",
                "scrapy_version": scrapy.__version__,
                "note": "Scrapy provides crawler framework capabilities to main scraper",
                "job_context": context,
            }
            self.save_metadata_json(metadata)
            return metadata
            
        except ImportError:
            error_data = {
                "tool_id": self.tool_id,
                "status": "not_installed",
                "error": "Scrapy package not found",
                "install_command": "pip install scrapy",
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
    adapter = ScrapyAdapter()
    result = adapter.run()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
