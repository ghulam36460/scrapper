# Scraper Expert SKILL

**Purpose:** A master skill that encapsulates all scraper best-practices. Include this as the overarching guide for any advanced scraping task.

## Project Philosophy
- Treat web scraping as a data engineering project, not a quick script. Design for maintainability and scale from the start.
- **Legality and Ethics:** Only scrape publicly available factual data (e.g. product names, prices). Avoid copyrighted or personal content unless allowed.
- **Modularity:** Always factor code into reusable modules (as per `scraper-architecture`) and apply other SKILLs consistently.
- **Politeness:** Rate-limit and back off on failures. Provide contact info or honor `robots.txt` crawl delays.
- **Metrics:** Track success/failure rates, response times, and volume of data harvested for monitoring.

## Key Guidelines (Inherited from other SKILLs)
- **Architecture:** Use a `BaseScraper` and clear modules (fetching, parsing, storing). Favor composition and clean interfaces.
- **Style:** Follow consistent naming and formatting. Use type hints and docstrings. Avoid commented-out code.
- **Browser Use:** Reuse headless Playwright browsers and contexts, apply async fetch for concurrency.
- **Anti-Detection:** Rotate UAs and proxies. Use stealth drivers (e.g. `undetected-chromedriver`) if blocking is severe.
- **Data Pipeline:** Clean text, normalize numbers/dates, validate with a schema, and dedupe records.
- **Testing:** All new code must have unit tests. Use mocking for external calls, run tests in CI.
- **Git:** Feature-branch workflow, clear commits, PR reviews (see `git-workflow` SKILL).

## Do
- ✓ **Do** refer to this master skill by name in prompts to inherit all other rules, avoiding repetition.  
- ✓ **Do** use code templates or scaffolding (e.g. cookiecutter) that implement these patterns.  
- ✓ **Do** check against this SKILL after generation: the master skill serves as a checklist of best-practices.

## Avoid
- ✗ **Avoid** one-off hacks that violate any above rules, even if they seem to solve a quick problem. Instead, refactor or create exceptions only when absolutely necessary and document it.  
- ✗ **Avoid** re-specifying already-covered rules in prompt; instead rely on this SKILL’s inclusion.

## Token-Saving Tips
- 📌 **Umbrella prompt:** Simply stating “Follow the *Scraper Expert* guidelines” invokes all sub-skills, saving you from rewriting each rule set.  
- 📌 **Reference earlier skills:** The model will have read all SKILLs, so use phrases like “as defined above” instead of quoting them again.  
- 📌 **Chain commands:** Use concise phrases like “apply cache and batching” rather than describing each step if this SKILL is active.

