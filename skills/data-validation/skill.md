
### 5. `data-validation/SKILL.md`

```markdown
# Data Validation and Cleaning SKILL

**Purpose:** Specify how to validate and clean scraped data before storage. Use for any prompt that processes scraped fields.

## Rules
- **Schema enforcement:** Define a schema (e.g. with Pydantic or a database schema) for expected fields and types. Every record should validate against this schema; raise/log errors on failure.  
- **Trim and normalize text:** Strip whitespace, decode HTML entities, normalize Unicode characters.  
- **Standardize formats:** Convert dates to a uniform format (ISO `YYYY-MM-DD`) and parse numbers to numeric types (remove currency symbols, commas).  
- **Deduplication:** Remove duplicate records (e.g. based on unique ID or hash of key fields). Ensure only the most recent data is kept if time-stamped.  
- **Missing data:** If fields are missing or invalid, either fill with defaults or skip the record. Log any missing-critical-field occurrences.  
- **Confidence scoring:** Optionally assign a quality score per record (e.g. 0–1) based on completeness or parse success rate. Lower score if many fields required manual fixing.

## Examples
- **Pydantic schema (example):**  
  ```python
  from pydantic import BaseModel, HttpUrl, validator
  from datetime import datetime

  class ScrapedProduct(BaseModel):
      name: str
      price: float
      currency: str = "USD"
      url: HttpUrl
      scraped_at: datetime

      @validator("price")
      def check_price(cls, v):
          if v <= 0: raise ValueError("Price must be positive")
          return round(v, 2)
