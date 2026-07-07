"""
Unified service for formatting and normalizing business data for professional exports.
"""

from __future__ import annotations
import re
from typing import Any

# Map Country Code to Intl Prefix
COUNTRY_PREFIXES = {
    "PK": "+92", "US": "+1", "CA": "+1", "GB": "+44", "AE": "+971",
    "IN": "+91", "SA": "+966", "AU": "+61", "DE": "+49", "FR": "+33",
    "BD": "+880", "NG": "+234", "EG": "+20", "ZA": "+27"
}

# Map Country Code to Full Name
COUNTRY_NAMES = {
    "PK": "Pakistan", "US": "USA", "CA": "Canada", "GB": "United Kingdom",
    "AE": "UAE", "IN": "India", "SA": "Saudi Arabia", "AU": "Australia",
    "DE": "Germany", "FR": "France", "BD": "Bangladesh", "NG": "Nigeria",
    "EG": "Egypt", "ZA": "South Africa"
}

class DataFormatter:
    
    @staticmethod
    def format_phone(number: Any, country_code: str = "") -> str:
        if not number or str(number).strip() == "-":
            return "-"
        
        num_str = "{:.0f}".format(float(number)) if isinstance(number, (int, float)) else str(number)
        digits = re.sub(r"\D", "", num_str)
        
        prefix = COUNTRY_PREFIXES.get(country_code.upper(), "")
        prefix_digits = prefix.replace("+", "")
        
        # Remove existing prefix if present
        if digits.startswith(prefix_digits):
            digits = digits[len(prefix_digits):]
        
        # Exact format: +CC NNN NNNNNNN
        # digits example for +92 321 1234567 is 3211234567
        # So: +CC (digits[:3]) (digits[3:])
        return f"+{prefix_digits} {digits[:3]} {digits[3:]}".strip()

    @staticmethod
    def format_boolean(value: Any) -> str:
        val = str(value).lower().strip()
        if val in {"yes", "true", "1"}:
            return "✅"
        elif val in {"no", "false", "0"}:
            return "❌"
        return "-"

    @staticmethod
    def format_score(value: Any) -> str:
        try:
            return f"{float(value) * 100:.0f}%"
        except (TypeError, ValueError):
            return "-"

    @staticmethod
    def format_url(url: Any) -> str:
        if not url:
            return "-"
        # Keep only domain
        try:
            return re.sub(r'^(https?://)?(www\.)?', '', str(url)).rstrip('/')
        except:
            return str(url)

    @staticmethod
    def format_country(code: Any) -> str:
        return COUNTRY_NAMES.get(str(code).upper(), str(code))
