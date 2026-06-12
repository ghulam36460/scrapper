"""
ASAGUS Adapter for Outreach System
Lead scoring and outreach pipeline integration.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from unified_tool_adapter import UnifiedToolAdapter


class OutreachSystemAdapter(UnifiedToolAdapter):
    """Adapter for outreach system with lead scoring."""
    
    def run(self):
        """Run outreach system with ASAGUS job context."""
        context = self.get_job_context()
        
        try:
            # Import lead scorer
            sys.path.insert(0, str(Path(__file__).parent))
            from lead_scorer import score_and_segment_lead
            
            # This is a post-processing tool, not a scraper
            # It scores leads that have already been scraped
            metadata = {
                "tool_id": self.tool_id,
                "status": "ready",
                "message": "Outreach system ready for lead scoring",
                "note": "This tool scores and segments leads after they are scraped",
                "dry_run_only": True,  # By design, doesn't send emails without explicit configuration
                "job_context": context,
            }
            self.save_metadata_json(metadata)
            return metadata
            
        except ImportError as e:
            error_data = {
                "tool_id": self.tool_id,
                "status": "import_error",
                "error": f"Could not import lead_scorer: {str(e)}",
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
    adapter = OutreachSystemAdapter()
    result = adapter.run()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
