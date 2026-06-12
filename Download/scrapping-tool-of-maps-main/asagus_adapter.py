"""
ASAGUS Adapter for Maps Scraper
Makes the maps scraper work with the unified ASAGUS pipeline.
"""
import sys
from pathlib import Path

# Add parent directory to path for unified adapter
sys.path.insert(0, str(Path(__file__).parent.parent))
from unified_tool_adapter import UnifiedToolAdapter


class MapsScraperAdapter(UnifiedToolAdapter):
    """Adapter for Google Maps scraper tool."""
    
    def run(self):
        """Run the maps scraper with ASAGUS job context."""
        context = self.get_job_context()
        
        if not self.real_run:
            # Dry run - return sample data
            sample_data = {
                "tool_id": self.tool_id,
                "status": "dry_run",
                "message": "Dry run completed - no real scraping performed",
                "job_context": context,
                "output_csv": str(self.csv_path),
            }
            self.save_metadata_json(sample_data)
            return sample_data
        
        try:
            # Import the actual scraper
            sys.path.insert(0, str(Path(__file__).parent / "backend"))
            from enhanced_scraper import EnhancedGoogleMapsScraper
            
            # Create scraper instance
            scraper = EnhancedGoogleMapsScraper(
                max_results=self.limit,
                headless=True,
                website_filter=self.website_filter,
                concurrent_extractions=4 if self.mode == "max" else 2,
            )
            
            # Run scraper synchronously
            results = scraper.scrape_sync(self.query, self.location)
            
            # Save to unified CSV
            self.save_records_csv(results)
            
            # Save metadata
            metadata = {
                "tool_id": self.tool_id,
                "status": "completed",
                "records_found": len(results),
                "job_context": context,
                "output_csv": str(self.csv_path),
                "output_json": str(self.json_path),
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
    """Entry point for ASAGUS integration."""
    import json
    adapter = MapsScraperAdapter()
    result = adapter.run()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
