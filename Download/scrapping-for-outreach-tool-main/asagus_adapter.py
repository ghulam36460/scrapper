"""
ASAGUS Adapter for Outreach Scraper
Makes the outreach scraper work with the unified ASAGUS pipeline.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from unified_tool_adapter import UnifiedToolAdapter


class OutreachScraperAdapter(UnifiedToolAdapter):
    """Adapter for outreach contact scraper tool."""
    
    def run(self):
        """Run the outreach scraper with ASAGUS job context."""
        context = self.get_job_context()
        
        if not self.real_run:
            sample_data = {
                "tool_id": self.tool_id,
                "status": "dry_run",
                "message": "Dry run completed",
                "job_context": context,
            }
            self.save_metadata_json(sample_data)
            return sample_data
        
        try:
            # Import the actual scraper
            sys.path.insert(0, str(Path(__file__).parent / "backend"))
            from enhanced_scraper import EnhancedGoogleMapsScraper
            
            # Create scraper focusing on contact information
            scraper = EnhancedGoogleMapsScraper(
                max_results=self.limit,
                headless=True,
                website_filter="all",  # Get all to extract contacts
                concurrent_extractions=3,
            )
            
            # Run scraper
            results = scraper.scrape_sync(self.query, self.location)
            
            # Save to unified CSV
            self.save_records_csv(results)
            
            metadata = {
                "tool_id": self.tool_id,
                "status": "completed",
                "records_found": len(results),
                "job_context": context,
                "output_csv": str(self.csv_path),
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
    adapter = OutreachScraperAdapter()
    result = adapter.run()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
