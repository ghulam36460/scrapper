"""
Example: Integrating AntiBot Framework into ASAGUS Scraper
===========================================================

This file demonstrates practical usage patterns for the 5-layer
anti-bot architecture within the existing ASAGUS scraper.
"""

from __future__ import annotations

import asyncio
import logging

import playwright.async_api as pw

from asagus.layers.antibot_orchestrator import (
    create_antibot_orchestrator,
    AntiBotConfig,
)
from asagus.layers.antibot_layer2_stealth import StealthApproach
from asagus.layers.antibot_layer3_tls import BrowserTLSFingerprint


logger = logging.getLogger(__name__)


# ============================================================================
# EXAMPLE 1: High-Stealth Browser Automation
# ============================================================================
# Use case: Scraping a heavily protected site with bot detection
# Target: Financial data, security-conscious sites, government sites

async def example_high_stealth_scraping():
    """
    Example: Scraping with maximum anti-bot protection.
    
    Uses:
    - Layer 2: Camoufox binary-patch stealth (0% detection)
    - Layer 3: Chrome 124 Windows TLS fingerprint
    - Layer 4: Realistic Windows laptop device profile
    - Layer 5: Human-like behavioral simulation
    """
    
    # Configure for maximum stealth
    config = AntiBotConfig(
        framework_priority=\"stealth\",
        stealth_approach=StealthApproach.camoufox,  # ★★★ Best
        tls_fingerprint=BrowserTLSFingerprint.chrome_124_windows,
        device_profile_name=\"windows_chrome\",
        enable_behavioral_simulation=True,
        enable_consistency_checks=True,
    )
    
    orchestrator = create_antibot_orchestrator(config)
    
    # Print status
    print(orchestrator.get_status_report())
    
    # Launch browser
    async with await pw.async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        try:
            # Setup browser context with all anti-bot layers
            context = await orchestrator.setup_browser_context(
                browser,
                url=\"https://target.com\"
            )
            
            page = await context.new_page()
            
            # Navigate to target
            await page.goto(\"https://target.com\", wait_until=\"domcontentloaded\")
            
            # Human-like interactions using Layer 5
            behavior = orchestrator.layer5_behavior
            
            # Move mouse naturally to button
            await behavior.move_mouse_human_like(page, 500, 300)
            
            # Click with natural behavior (dwell, micro-jitter)
            await behavior.click_human_like(page, 500, 300)
            
            # Type with realistic patterns (variable timing, errors)
            await behavior.type_human_like(page, \"search query\")
            
            # Wait like a human would read
            await behavior.wait_and_read_like_human(page, estimated_words=300)
            
            # Get consistency report
            consistency = orchestrator.get_cross_layer_consistency_report()
            logger.info(f\"Consistency: {consistency}\")
            
            # Extract content
            content = await page.content()
            
        finally:
            await browser.close()


# ============================================================================
# EXAMPLE 2: High-Throughput HTTP-Only Scraping
# ============================================================================
# Use case: Scraping API endpoints or server-rendered pages
# Target: News sites, public data, high-volume crawling

async def example_high_throughput_scraping():
    \"\"\"
    Example: High-throughput HTTP scraping with TLS impersonation.
    
    Uses:
    - Layer 1: Automatically selects curl-cffi (HTTP-only, 10-50x faster)
    - Layer 3: Chrome 124 TLS fingerprint via curl-cffi
    - Layer 2: Stealth HTTP headers
    - No browser overhead = perfect for high-volume
    
    Performance: ~50-200 requests/sec vs ~0.5-2 for browser automation
    \"\"\"
    
    # Configure for speed (framework selector will choose curl-cffi)
    config = AntiBotConfig(
        framework_priority=\"speed\",
        tls_fingerprint=BrowserTLSFingerprint.chrome_124_windows,
        enable_behavioral_simulation=False,  # Not needed for HTTP
    )
    
    orchestrator = create_antibot_orchestrator(config)
    
    # Create HTTP client with TLS impersonation
    # Layer 1 auto-selects curl-cffi for HTTP-only targets
    client = await orchestrator.create_http_client(\"https://api.target.com\")
    
    # Fetch multiple URLs with TLS stealth
    urls = [
        \"https://api.target.com/data/page1\",
        \"https://api.target.com/data/page2\",
        \"https://api.target.com/data/page3\",
    ]
    
    for url in urls:
        response = await client.get(url)
        # Response has:
        # - Layer 3: curl-cffi with Chrome 124 TLS fingerprint
        # - Layer 2: Stealth HTTP headers injected
        # - JA3 hash matches declared User-Agent
        data = response.json()
        logger.info(f\"Fetched {url}: {len(data)} items\")


# ============================================================================
# EXAMPLE 3: Target-Specific Configuration
# ============================================================================
# Different targets need different strategies

async def scrape_target_specific():
    \"\"\"
    Example: Adjusting configuration per target type.
    \"\"\"
    
    targets = [
        {
            \"url\": \"https://news.site.com\",
            \"strategy\": \"high_throughput\",
            \"description\": \"News site - HTTP-only, no JS\",
        },
        {
            \"url\": \"https://spa.target.com\",
            \"strategy\": \"browser\",
            \"description\": \"Single-page app - needs browser\",
        },
        {
            \"url\": \"https://banking.target.com\",
            \"strategy\": \"maximum_stealth\",
            \"description\": \"Banking site - heavy bot detection\",
        },
    ]
    
    for target in targets:
        logger.info(f\"Scraping {target['url']} with {target['strategy']} strategy\")
        
        if target[\"strategy\"] == \"high_throughput\":
            # HTTP-only scraping
            config = AntiBotConfig(
                framework_priority=\"speed\",
                enable_behavioral_simulation=False,
            )
        
        elif target[\"strategy\"] == \"browser\":
            # Standard browser automation
            config = AntiBotConfig(
                framework_priority=\"compatibility\",
                stealth_approach=StealthApproach.javascript_shim,
            )
        
        elif target[\"strategy\"] == \"maximum_stealth\":
            # Maximum protection
            config = AntiBotConfig(
                framework_priority=\"stealth\",
                stealth_approach=StealthApproach.camoufox,
                enable_behavioral_simulation=True,
                enable_consistency_checks=True,
            )
        
        orchestrator = create_antibot_orchestrator(config)
        
        # Use orchestrator for this target
        # (actual scraping logic would go here)
        print(orchestrator.get_status_report())


# ============================================================================
# EXAMPLE 4: Debugging & Validation
# ============================================================================

async def example_debugging():
    \"\"\"
    Example: Using diagnostic tools to validate anti-bot configuration.
    \"\"\"
    
    config = AntiBotConfig()
    orchestrator = create_antibot_orchestrator(config)
    
    # Get full status report
    print(\"\\n\" + orchestrator.get_status_report())
    
    # Get consistency report
    consistency = orchestrator.get_cross_layer_consistency_report()
    print(\"\\nConsistency Report:\")
    print(f\"  Consistent: {consistency['consistent']}\")
    if consistency[\"warnings\"]:
        print(\"  Warnings:\")
        for warning in consistency[\"warnings\"]:
            print(f\"    - {warning}\")
    
    # Get detailed layer info
    print(\"\\nLayer Information:\")
    for layer, info in consistency[\"layer_info\"].items():
        print(f\"  {layer}: {info}\")
    
    # TLS fingerprint details
    tls_info = orchestrator.layer3_tls.get_fingerprint_info()
    print(\"\\nTLS Fingerprint Details:\")
    print(f\"  Fingerprint: {tls_info['fingerprint_type']}\")
    print(f\"  JA3 Hash: {tls_info['ja3_hash']}\")
    print(f\"  HTTP/2 Settings: {tls_info['http2_settings']}\")
    print(f\"  ALPN Protocols: {tls_info['alpn_protocols']}\")
    
    # Device profile
    print(\"\\nDevice Profile:\")
    print(orchestrator.layer4_fingerprinting.get_device_profile_json())


# ============================================================================
# EXAMPLE 5: Integration with Existing ASAGUS Layers
# ============================================================================

async def example_asagus_integration():
    \"\"\"
    Example: How to integrate AntiBot orchestrator with ASAGUS layers.
    
    This shows how the antibot framework fits into the existing
    ASAGUS architecture (fetch, extraction, storage, etc.)
    \"\"\"
    
    from asagus.layers.fetch import FetchLayer
    from asagus.layers.extraction import ExtractionLayer
    from asagus.layers.storage import StorageLayer
    
    config = AntiBotConfig(
        stealth_approach=StealthApproach.javascript_shim,
        enable_behavioral_simulation=True,
    )
    orchestrator = create_antibot_orchestrator(config)
    
    # Example URL to scrape
    url = \"https://target.com/data\"
    
    # Step 1: Setup anti-bot protection for fetch layer
    async with await pw.async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await orchestrator.setup_browser_context(browser, url)
        page = await context.new_page()
        
        # Step 2: Fetch with anti-bot protection
        # (FetchLayer would use this protected page)
        await page.goto(url, wait_until=\"domcontentloaded\")
        
        # Use behavioral simulation for interactions
        await orchestrator.layer5_behavior.wait_and_read_like_human(
            page,
            estimated_words=500
        )
        
        # Step 3: Extract content
        content = await page.content()
        
        # Step 4: Pass to ASAGUS extraction layer
        # (existing ASAGUS code)
        # extracted = extraction_layer.extract(content, selectors)
        # storage_layer.store(extracted)


# ============================================================================
# EXAMPLE 6: Error Handling & Fallback
# ============================================================================

async def example_error_handling():
    \"\"\"
    Example: Handling detection and implementing fallback strategies.
    \"\"\"
    
    config = AntiBotConfig(
        stealth_approach=StealthApproach.camoufox,
        enable_behavioral_simulation=True,
    )
    orchestrator = create_antibot_orchestrator(config)
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with await pw.async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await orchestrator.setup_browser_context(
                    browser,
                    \"https://target.com\"
                )
                page = await context.new_page()
                
                # Add detection detection
                response = await page.goto(\"https://target.com\")
                
                if response.status == 403 or response.status == 429:
                    raise RuntimeError(\"Likely blocked by bot detection\")
                
                # Success
                content = await page.content()
                logger.info(\"Successfully scraped\")
                break
        
        except RuntimeError as e:
            logger.warning(f\"Attempt {attempt + 1} failed: {e}\")
            
            if attempt < max_retries - 1:
                # Fallback to different strategy
                if orchestrator.config.stealth_approach == StealthApproach.camoufox:
                    logger.info(\"Falling back to JavaScript shim approach\")\n                    orchestrator.config.stealth_approach = StealthApproach.javascript_shim
                else:
                    logger.info(\"Fallback failed, implementing delay\")\n                    await asyncio.sleep(5 * (attempt + 1))


# ============================================================================
# EXAMPLE 7: Batch Processing with Anti-Bot
# ============================================================================

async def example_batch_processing():
    \"\"\"
    Example: Processing many URLs with shared anti-bot orchestrator.
    \"\"\"
    
    config = AntiBotConfig(
        framework_priority=\"speed\",
        tls_fingerprint=BrowserTLSFingerprint.chrome_124_windows,
    )
    orchestrator = create_antibot_orchestrator(config)
    
    urls = [
        \"https://example.com/article/1\",
        \"https://example.com/article/2\",
        \"https://example.com/article/3\",
        # ... many more URLs
    ]
    
    # Use HTTP client for batch (faster than browser)
    client = await orchestrator.create_http_client()
    
    results = []
    for url in urls:
        try:
            response = await client.get(url, timeout=10)
            data = response.json() if response.headers.get(\"content-type\") == \"application/json\" else response.text
            results.append({
                \"url\": url,
                \"status\": response.status_code,
                \"data\": data
            })
        except Exception as e:
            logger.error(f\"Error fetching {url}: {e}\")
    
    return results


# ============================================================================
# Main: Run Examples
# ============================================================================

async def main():
    \"\"\"Run all examples.\"\"\"
    
    logging.basicConfig(level=logging.INFO)
    
    print(\"\\n\" + \"=\"*70)
    print(\"EXAMPLE 1: Debugging & Validation\")
    print(\"=\"*70)
    await example_debugging()
    
    # Note: Other examples would require actual targets
    # print(\"\\n\" + \"=\"*70)
    # print(\"EXAMPLE 2: High-Stealth Scraping\")
    # print(\"=\"*70)
    # await example_high_stealth_scraping()


if __name__ == \"__main__\":
    asyncio.run(main())
