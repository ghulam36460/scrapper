# Scraper Architecture SKILL

**Purpose:** Provides guidelines for organizing scraper code into modules and classes for clarity, reuse, and token efficiency. Include this skill on any code generation task that defines or refactors scraper structure.

## Rules
- Define a **BaseScraper** class with core functionality (browser launch, requests, error handling). Other scrapers must subclass it.
- Keep **concerns separated**: one module/class for fetching pages, another for parsing data, another for data storage.
- Use **dependency injection**: pass shared objects (e.g. HTTP session, DB connection, config) into classes to avoid globals.
- Use **config files** or constants for settings (URLs, timeouts) rather than hard-coding. Import these to shorten prompts.
- Always **log actions** (start/stop, errors) using a logger module, not print statements.
- Favor **composition over duplication**: if two scrapers share logic, factor that into a reusable function or mix-in class.
- Use **meaningful names** (e.g. `AmazonScraper`, `ProductParser`, `DatabaseWriter`) to clarify role and let prompts use short names.

## Examples
- **Bad (no base class):**
  ```python
  # scraper.py
  import requests
  def scrape_site(): ...
  def parse_data(html): ...
  def save_to_db(data): ...
