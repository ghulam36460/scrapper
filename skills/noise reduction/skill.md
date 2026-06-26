Noise-Reduction Data Pipeline
Goal: Clean and normalize raw scraped data to ensure high-quality output.

Identify noisy fields: During scraping, track fields with inconsistent formats or missing data (e.g. prices with currency symbols, dates in different formats, HTML tags in text, non-ASCII characters). Common issues include missing price/ID, text encoding glitches, and HTML entities (e.g. &amp;).

Schema design: Define a formal schema (e.g. a database table or Pydantic model) for each entity (Product, Article, etc). Include types (string, numeric, datetime) and constraints (non-null for essential fields). Example schema snippet:

python
Copy
class Product(BaseModel):
    id: str
    name: str
    price: float
    currency: str = "USD"
    date: date
Normalization rules:

Trim whitespace and remove HTML tags/entities: use html.unescape and str.strip().
Unicode normalization: apply unicodedata.normalize("NFKD", text) to fix encoding issues.
Numeric parsing: Strip currency symbols and thousands separators, handle decimal formats (see example in [55†L141-L150]). E.g.: convert "$1,299.00" → 1299.00.
Date parsing: Use a date parser (e.g. dateutil.parser.parse) to accept formats like "Mar 9, 2026" or "2026-03-09", outputting ISO dates.
Case normalization: Convert fields like category or city to consistent case (e.g. lowercase or titlecase).
Deduplication:

Before insert, detect duplicates. For instance, use a combination of unique fields as a key (e.g. URL or (name,price)). Maintain a set or use database uniqueness constraints.
Example pseudocode:
python
Copy
seen = set()
unique_rows = []
for row in scraped_rows:
    key = row["id"] or (row["url"], row["name"])
    if key in seen:
        continue
    seen.add(key)
    unique_rows.append(row)
In databases, use ON CONFLICT or INSERT IGNORE to drop duplicates.
Confidence Scoring: Assign a confidence level (0-1) for each record based on validation results. For example:

Start at 1.0. Subtract points for each minor issue (e.g. missing non-critical field: -0.1, currency mismatch: -0.2, parse error: -0.5).
A record with any failed required field might get 0 or be dropped.
Schema Enforcement & Validation:

Use a validation library (e.g. Pydantic) to enforce types and value constraints (as shown in [55†L70-L79]). Validation will automatically clean fields and raise errors for bad data.
Example: if price is empty, Pydantic can replace it with None or throw a validation error for downstream logging.
Pipeline code (pseudocode/Python):

python
Copy
import html, unicodedata, re
from pydantic import BaseModel, validator
from datetime import datetime

class ScrapedProduct(BaseModel):
    name: str
    price: float
    currency: str = "USD"
    url: str
    scraped_date: datetime

    @validator('name', pre=True)
    def clean_name(cls, v):
        text = html.unescape(v)  # decode HTML
        text = unicodedata.normalize("NFKD", text)  # normalize unicode
        return " ".join(text.split()).strip()

    @validator('price', pre=True)
    def parse_price(cls, v):
        s = re.sub(r"[^\d.,]", "", str(v))
        s = s.replace(",", "")
        try:
            return float(s)
        except:
            raise ValueError("Invalid price")

    @validator('scraped_date', pre=True)
    def parse_date(cls, v):
        try:
            return datetime.strptime(v, "%b %d, %Y")
        except:
            return datetime.fromisoformat(v)

# Usage example:
raw = {"name": "<b>Gadget</b>", "price": "$1,299.00", "url": "http://x", "scraped_date": "Mar 9, 2026"}
product = ScrapedProduct(**raw)  # cleans fields, raises on failure
This approach ensures every field is normalized and valid.

Batching: Perform validation/cleaning in batches rather than one row at a time if large. This can use DataFrame operations (e.g. pandas’ apply) or Python loops over chunks.

Logging: Log any records with low confidence or validation errors for manual review. For automated pipelines, track error counts as metrics.