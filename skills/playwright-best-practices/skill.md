
### 3. `playwright-best-practices/SKILL.md`

```markdown
# Playwright Best Practices SKILL

**Purpose:** Guide Playwright usage for scraping dynamic pages in a performant and reliable way.

## Rules
- Launch one headless browser instance and **reuse it** for multiple pages. (Do not launch a new browser per URL.)
- Use **async APIs** (e.g. `async_playwright`) to fetch pages in parallel (e.g. `asyncio.gather` for multiple pages).
- When creating contexts: set `headless=True` for invisible mode, and configure `user_agent` with `context.set_extra_http_headers({"User-Agent": ...})` or `context.set_user_agent()` to mimic real browsers.
- Use `page.wait_for_load_state('networkidle')` or `page.wait_for_selector()` to ensure content loads before parsing.
- Avoid hardcoded sleeps; rely on explicit waits. Playwright’s auto-waiting often suffices.
- Close pages or contexts after use to free resources; close browser at end.
- Intercept or modify network requests if needed (e.g. block unnecessary resources via `route.abort()`).
- Handle timeouts and retries: use `page.goto(url, timeout=..., wait_until='networkidle')` and retry on failures.

## Examples
- **Reusing browser instance:**
  ```python
  from playwright.async_api import async_playwright
  async with async_playwright() as p:
      browser = await p.chromium.launch(headless=True)
      context = await browser.new_context(user_agent="Mozilla/5.0 ...")
      page = await context.new_page()
      await page.goto("https://example.com")
      content = await page.content()
      await browser.close()
