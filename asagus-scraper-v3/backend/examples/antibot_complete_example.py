"""
ASAGUS Scraper v3 - Complete Anti-Bot Evasion Example
======================================================
Demonstrates the complete 5-layer anti-bot evasion system with:
- All 5 detection layers (automation, stealth, TLS, fingerprinting, behavioral)
- CAPTCHA solving (reCAPTCHA, hCaptcha, Turnstile)
- Detection system handling (Cloudflare, DataDome, Akamai, etc.)
- Adaptive mode switching
- Proxy rotation
- Configuration management

Based on 2026 research from antibot.md
"""

import asyncio
import logging

import playwright.async_api as pw

from asagus.layers.antibot_orchestrator import create_antibot_orchestrator_from_config


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def example_basic_scraping():
    """Basic example: Scrape a single URL with full anti-bot protection."""
    
    logger.info("=" * 70)
    logger.info("Example 1: Basic Scraping with Anti-Bot Protection")
    logger.info("=" * 70)
    
    # Create orchestrator with "balanced" preset
    orchestrator = create_antibot_orchestrator_from_config(preset="balanced")
    
    # Launch browser
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Setup browser context with all anti-bot layers
        context = await orchestrator.setup_browser_context(
            browser,
            url="https://httpbin.org"
        )
        
        page = await context.new_page()
        
        # Navigate with detection handling
        logger.info("Navigating to target URL...")
        response = await page.goto("https://httpbin.org/headers")
        
        # Handle any detection challenges
        success = await orchestrator.handle_detection_response(
            page, response, url="https://httpbin.org/headers"
        )
        
        if success:
            logger.info("✓ Page loaded successfully")
            
            # Extract content
            content = await page.content()
            logger.info(f"Content length: {len(content)} bytes")
        else:
            logger.error("✗ Failed to handle detection")
        
        # Get statistics
        stats = orchestrator.get_detection_statistics()
        logger.info(f"Detection stats: {stats}")
        
        await browser.close()


async def example_with_proxy_pool():
    """Example with residential proxy pool."""
    
    logger.info("=" * 70)
    logger.info("Example 2: Scraping with Proxy Pool")
    logger.info("=" * 70)
    
    # Define proxy pool (replace with real proxies)
    proxy_urls = [
        # "http://username:password@proxy1.example.com:8080",
        # "http://username:password@proxy2.example.com:8080",
    ]
    
    # Create orchestrator with proxy pool
    orchestrator = create_antibot_orchestrator_from_config(
        preset="high-stealth",
        proxy_urls=proxy_urls if proxy_urls else None
    )
    
    logger.info("Proxy pool size: {}".format(
        len(orchestrator.proxy_manager.proxies) if orchestrator.proxy_manager else 0
    ))
    
    # Proxies will automatically rotate after 500 requests
    # Geolocation will be verified to match device timezone


async def example_adaptive_detection():
    """Example showing adaptive mode switching."""
    
    logger.info("=" * 70)
    logger.info("Example 3: Adaptive Detection Handling")
    logger.info("=" * 70)
    
    orchestrator = create_antibot_orchestrator_from_config(preset="balanced")
    
    # Print current configuration
    config = orchestrator.export_configuration()
    logger.info(f"Initial configuration: {config}")
    
    # Simulate detection events
    domain = "example.com"
    
    # Simulate 3 detections (should trigger proxy rotation)
    logger.info("Simulating 3 detections...")
    for i in range(3):
        await orchestrator.adaptive_controller.handle_detection(
            domain, status_code=403, captcha_detected=False
        )
    
    # Simulate 2 more detections (should trigger device profile rotation)
    logger.info("Simulating 2 more detections (total: 5)...")
    for i in range(2):
        await orchestrator.adaptive_controller.handle_detection(
            domain, status_code=403, captcha_detected=False
        )
    
    # Simulate 2 more detections (should trigger stealth approach change)
    logger.info("Simulating 2 more detections (total: 7)...")
    for i in range(2):
        await orchestrator.adaptive_controller.handle_detection(
            domain, status_code=403, captcha_detected=False
        )
    
    # Get adaptive statistics
    stats = orchestrator.adaptive_controller.get_statistics()
    logger.info(f"Adaptive stats: {stats}")


async def example_http_only_scraping():
    """Example: High-speed HTTP-only scraping (no browser)."""
    
    logger.info("=" * 70)
    logger.info("Example 4: HTTP-Only Scraping (10-50x faster)")
    logger.info("=" * 70)
    
    orchestrator = create_antibot_orchestrator_from_config(preset="high-speed")
    
    # Create HTTP client with TLS impersonation
    http_client = await orchestrator.create_http_client(
        url="https://httpbin.org/get"
    )
    
    logger.info("Making HTTP request with TLS impersonation...")
    
    # Make request (curl-cffi with Chrome 124 TLS fingerprint)
    try:
        response = await http_client.get("https://httpbin.org/get")
        logger.info(f"Status: {response.status_code}")
        logger.info(f"Response: {response.text[:200]}...")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await http_client.aclose()


async def example_captcha_detection():
    """Example: CAPTCHA detection and solving."""
    
    logger.info("=" * 70)
    logger.info("Example 5: CAPTCHA Detection")
    logger.info("=" * 70)
    
    orchestrator = create_antibot_orchestrator_from_config(preset="high-stealth")
    
    async with pw.async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Headed for CAPTCHA
        context = await orchestrator.setup_browser_context(
            browser,
            url="https://www.google.com/recaptcha/api2/demo"
        )
        
        page = await context.new_page()
        
        # Navigate to reCAPTCHA demo page
        logger.info("Loading reCAPTCHA demo page...")
        await page.goto("https://www.google.com/recaptcha/api2/demo")
        
        # Detect CAPTCHA
        captcha = await orchestrator.captcha_solver.detect_captcha(page)
        
        if captcha:
            logger.info(f"✓ Detected: {captcha.captcha_type.value}")
            logger.info(f"  Site key: {captcha.site_key}")
            
            # Note: Actual solving requires YOLOv8 model
            logger.info("  (Solving requires YOLOv8 model - not loaded in this demo)")
        else:
            logger.info("No CAPTCHA detected")
        
        await browser.close()


async def example_status_report():
    """Example: Get comprehensive status report."""
    
    logger.info("=" * 70)
    logger.info("Example 6: Status Report")
    logger.info("=" * 70)
    
    orchestrator = create_antibot_orchestrator_from_config(preset="high-stealth")
    
    # Print status report
    print(orchestrator.get_status_report())
    
    # Print consistency report
    report = orchestrator.get_cross_layer_consistency_report()
    logger.info(f"Cross-layer consistency: {report['consistent']}")
    if report['warnings']:
        logger.warning(f"Warnings: {report['warnings']}")
    
    # Print layer info
    for layer, info in report['layer_info'].items():
        logger.info(f"{layer}: {info}")


async def example_from_yaml_config():
    """Example: Load configuration from YAML file."""
    
    logger.info("=" * 70)
    logger.info("Example 7: Load from YAML Configuration")
    logger.info("=" * 70)
    
    # Load from YAML file
    # orchestrator = create_antibot_orchestrator_from_config(
    #     config_path="config/antibot_config.yaml"
    # )
    
    # For demo, use preset
    orchestrator = create_antibot_orchestrator_from_config(preset="balanced")
    
    # Export current configuration
    config = orchestrator.export_configuration()
    logger.info(f"Configuration: {config}")
    
    # Configuration can be hot-reloaded without restart
    # orchestrator.config_manager.hot_reload()


async def main():
    """Run all examples."""
    
    logger.info("╔" + "═" * 68 + "╗")
    logger.info("║" + " " * 5 + "ASAGUS Scraper v3 - Anti-Bot Evasion Examples" + " " * 17 + "║")
    logger.info("║" + " " * 12 + "Complete 5-Layer Detection Evasion" + " " * 22 + "║")
    logger.info("╚" + "═" * 68 + "╝")
    logger.info("")
    
    try:
        # Run examples
        await example_basic_scraping()
        await example_status_report()
        await example_http_only_scraping()
        await example_adaptive_detection()
        
        # Uncomment to run other examples:
        # await example_with_proxy_pool()
        # await example_captcha_detection()
        # await example_from_yaml_config()
        
        logger.info("")
        logger.info("✓ All examples completed successfully")
    
    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
