"""
ASAGUS Adapter for Outreach Mailer
Email outreach system integration.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from unified_tool_adapter import UnifiedToolAdapter


class OutreachMailerAdapter(UnifiedToolAdapter):
    """Adapter for outreach mailer system."""
    
    def run(self):
        """Run outreach mailer with ASAGUS job context."""
        context = self.get_job_context()
        
        try:
            # Outreach mailer is for sending emails, not scraping
            metadata = {
                "tool_id": self.tool_id,
                "status": "ready",
                "message": "Outreach mailer system ready",
                "note": "This tool sends outreach emails to scraped leads",
                "safety": "Dry run by default - requires explicit email configuration to send",
                "integration": "Use scraped data as input for email campaigns",
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
    adapter = OutreachMailerAdapter()
    result = adapter.run()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
