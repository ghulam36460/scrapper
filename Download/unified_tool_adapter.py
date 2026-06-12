"""
Unified Tool Adapter - Makes all Download tools work together on the same scraping target.
Each tool scrapes the same query/location and saves to the unified CSV format.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path
from typing import Any


class UnifiedToolAdapter:
    """Base adapter that all tools inherit from to ensure unified behavior."""
    
    def __init__(self):
        # Get job context from environment (set by main ASAGUS scraper)
        self.job_id = os.environ.get("ASAGUS_JOB_ID", "manual")
        self.query = os.environ.get("ASAGUS_QUERY", "")
        self.location = os.environ.get("ASAGUS_LOCATION", "")
        self.limit = int(os.environ.get("ASAGUS_LIMIT", "25"))
        self.mode = os.environ.get("ASAGUS_MODE", "balanced")
        self.website_filter = os.environ.get("ASAGUS_WEBSITE_FILTER", "all")
        self.tool_id = os.environ.get("ASAGUS_TOOL_ID", "unknown")
        
        # Output paths
        self.runs_root = Path(os.environ.get("ASAGUS_RUNS_ROOT", ".asagus-runs"))
        self.output_dir = self.runs_root / self.job_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # CSV output path (unified format)
        self.csv_path = self.output_dir / f"{self.tool_id}.csv"
        self.json_path = self.output_dir / f"{self.tool_id}.json"
        
        # Real run flag
        self.real_run = os.environ.get("ASAGUS_TOOL_REAL_RUN", "0") == "1"
        
    def normalize_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Normalize a record to unified CSV format."""
        normalized = {
            # Identity
            "name": "",
            "category": "",
            
            # Contact
            "phone": "",
            "whatsapp": "",
            "email": "",
            "address": "",
            
            # Location
            "city": "",
            "country_code": "",
            "lat": "",
            "lng": "",
            
            # Online presence
            "website_url": "",
            "facebook_url": "",
            "instagram_url": "",
            "twitter_url": "",
            "linkedin_url": "",
            
            # Ratings
            "rating": "",
            "review_count": "",
            
            # Metadata
            "source_tool": self.tool_id,
            "source_url": "",
            "description": "",
        }
        
        # Map various field names to unified format
        field_mappings = {
            # Name variations
            "business_name": "name",
            "title": "name",
            "company_name": "name",
            "business": "name",
            "place_name": "name",
            
            # Category variations
            "category": "category",
            "business_type": "category",
            "type": "category",
            "industry": "category",
            "categories": "category",
            
            # Phone variations
            "phone": "phone",
            "phone_number": "phone",
            "telephone": "phone",
            "tel": "phone",
            "contact_number": "phone",
            
            # WhatsApp variations
            "whatsapp": "whatsapp",
            "whatsapp_number": "whatsapp",
            "wa": "whatsapp",
            
            # Email variations
            "email": "email",
            "email_address": "email",
            "contact_email": "email",
            
            # Address variations
            "address": "address",
            "location": "address",
            "full_address": "address",
            "street_address": "address",
            
            # City variations
            "city": "city",
            "town": "city",
            "locality": "city",
            
            # Country variations
            "country": "country_code",
            "country_code": "country_code",
            
            # Coordinates
            "latitude": "lat",
            "lat": "lat",
            "longitude": "lng",
            "lng": "lng",
            "lon": "lng",
            
            # Website variations
            "website": "website_url",
            "website_url": "website_url",
            "url": "website_url",
            "web": "website_url",
            "site": "website_url",
            
            # Social variations
            "facebook": "facebook_url",
            "facebook_url": "facebook_url",
            "fb_url": "facebook_url",
            
            "instagram": "instagram_url",
            "instagram_url": "instagram_url",
            "ig_url": "instagram_url",
            
            "twitter": "twitter_url",
            "twitter_url": "twitter_url",
            "x_url": "twitter_url",
            
            "linkedin": "linkedin_url",
            "linkedin_url": "linkedin_url",
            
            # Ratings
            "rating": "rating",
            "stars": "rating",
            "score": "rating",
            
            "reviews": "review_count",
            "review_count": "review_count",
            "reviews_count": "review_count",
            "total_reviews": "review_count",
            
            # Metadata
            "source_url": "source_url",
            "url_source": "source_url",
            "description": "description",
            "about": "description",
        }
        
        # Apply mappings
        for original_key, value in record.items():
            if not value or value == "":
                continue
            
            # Normalize key
            key_lower = str(original_key).lower().replace("-", "_").replace(" ", "_")
            mapped_key = field_mappings.get(key_lower, key_lower)
            
            # Set value if normalized key exists in output
            if mapped_key in normalized:
                if not normalized[mapped_key]:  # Don't overwrite existing values
                    normalized[mapped_key] = str(value).strip()
        
        return normalized
    
    def save_records_csv(self, records: list[dict[str, Any]]):
        """Save records to CSV in unified format."""
        if not records:
            return
        
        normalized_records = [self.normalize_record(rec) for rec in records]
        
        # Define field order
        fieldnames = [
            "name", "category",
            "phone", "whatsapp", "email", "address",
            "city", "country_code", "lat", "lng",
            "website_url", "facebook_url", "instagram_url", "twitter_url", "linkedin_url",
            "rating", "review_count",
            "source_tool", "source_url", "description",
        ]
        
        with open(self.csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for record in normalized_records:
                writer.writerow(record)
    
    def save_metadata_json(self, metadata: dict[str, Any]):
        """Save tool execution metadata."""
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    def get_job_context(self) -> dict[str, Any]:
        """Get the job context for this run."""
        return {
            "job_id": self.job_id,
            "query": self.query,
            "location": self.location,
            "limit": self.limit,
            "mode": self.mode,
            "website_filter": self.website_filter,
            "real_run": self.real_run,
        }


def get_llm_config() -> dict[str, str]:
    """Get LLM configuration from environment."""
    return {
        "provider": os.environ.get("LLM_PROVIDER", "disabled"),
        "api_key": os.environ.get("LLM_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("OPENAI_API_KEY", ""),
        "model": os.environ.get("LLM_MODEL", ""),
        "base_url": os.environ.get("LLM_BASE_URL", ""),
    }


def get_proxy_config() -> dict[str, str]:
    """Get proxy configuration from environment."""
    return {
        "residential": os.environ.get("RESIDENTIAL_PROXY_URL", ""),
        "datacenter": os.environ.get("DATACENTER_PROXY_URL", ""),
    }
