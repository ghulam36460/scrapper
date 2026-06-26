
### 4. `anti-bot-strategies/SKILL.md`

```markdown
# Anti-Bot and Proxy Strategies SKILL

**Purpose:** Describe tactics to evade anti-scraping defenses. Use when generating code or configuration for scraping.

## Rules
- **Rotate User-Agent (UA):** On each request or each new browser context, pick a UA from a broad pool of realistic strings.  
- **Rotate Proxies:** Use a pool of proxy IPs (residential or datacenter). Distribute requests so no two consecutive requests use the same proxy or same IP subnet.  
- **Use backoff and throttling:** On HTTP errors or CAPTCHAs, wait and retry. Exponential backoff is recommended (e.g. double wait time after each failure, up to a limit).  
- **Handle CAPTCHAs:** Detect CAPTCHAs (e.g. by checking response content or status) and pass them to a solver service.  
- **Employ anti-detection tools:** For Selenium, use `undetected-chromedriver` to patch ChromeDriver fingerprints. For Playwright, consider stealth plugins or manipulating WebGL/canvas attributes (less mature).  

## Examples
- **UA rotation code snippet:**  
  ```python
  import random
  USER_AGENTS = [ "Mozilla/5.0 ...", "Chrome/xx ...", ... ]
  ua = random.choice(USER_AGENTS)
  context.set_extra_http_headers({"User-Agent": ua})
