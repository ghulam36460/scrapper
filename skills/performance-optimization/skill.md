
### 6. `performance-optimization/SKILL.md`

```markdown
# Performance & Cost Optimization SKILL

**Purpose:** Advise on making the scraper faster and more resource-efficient (reducing compute cost and tokens in prompts).

## Rules
- **Async/Concurrency:** Use asynchronous requests or concurrent browser pages to parallelize I/O. In Python, use `asyncio.gather` or threading for independent fetches.  
- **Reuse browser/contexts:** Launch the Playwright/selenium browser *once*, and reuse it (or its contexts) for multiple pages. Minimize new launches, since each is expensive.  
- **Page-level caching:** Cache static resources (CSS/JS) or API responses if site allows, to avoid re-downloading for similar pages. Use `page.route` in Playwright to serve from cache.  
- **Batch database writes:** Collect scraped data in memory or a buffer, then write in bulk to the database to reduce transaction overhead (e.g. insert many rows in one query).  
- **Selective rendering:** Disable loading images, CSS or ads in the browser if they are not needed (`page.route("**/*.{png,jpg,css}", route.abort)` in Playwright).  
- **Lightweight alternatives:** If a site offers JSON or API endpoints, prefer them over browser automation (dramatically cheaper and faster).  
- **Memory management:** Periodically clear large variables/lists and close pages/contexts to free memory in long runs.

## Examples
- **Async fetch:**  
  ```python
  async with async_playwright() as p:
      browser = await p.chromium.launch()
      context = await browser.new_context()
      pages = [await context.new_page() for _ in range(5)]
      tasks = [page.goto(url) for page, url in zip(pages, url_list)]
      await asyncio.gather(*tasks)
