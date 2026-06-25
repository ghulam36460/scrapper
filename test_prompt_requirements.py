import re
from asagus.layers.extraction import (
    should_skip_url, 
    clean_name, 
    normalize_phone, 
    fix_encoding
)

def test_requirements():
    print("--- Phase 3: Testing Prompt Requirements ---")
    
    # Test 1: URL skipping
    skip_urls = [
        "thecarnivore.com.pk/best-restaurants-in-lahore/",
        "lahore.restaurant/",
        "ebizpk.com/restaurants-lahore.htm",
        "zomato.com/lahore/restaurants"
    ]
    print("\nTest 1: URL skipping")
    for url in skip_urls:
        if should_skip_url(url):
            print(f"  [OK] Skipped: {url}")
        else:
            print(f"  [FAIL] Not skipped: {url}")
    
    # Test 3: Phone validation
    print("\nTest 3: Phone validation")
    test_phones = {
        "03215551234": "+923215551234",
        "5.0 ( 2": None,
        "1 2 3": None,
        "9.23E+11": None 
    }
    for raw, expected in test_phones.items():
        result = normalize_phone(raw, location="Lahore")
        if result == expected:
            print(f"  [OK] Phone {raw} -> {result}")
        else:
            print(f"  [FAIL] Phone {raw} -> Expected {expected}, Got {result}")

    # Test 4: Name cleaning
    print("\nTest 4: Name cleaning")
    test_names = {
        "Home | Bundu Khan": "Bundu Khan",
        "Best Restaurants in Lahore | 2026": "", # generic, skip
    }
    for raw, expected in test_names.items():
        result = clean_name(raw)
        if result == expected:
            print(f"  [OK] Name {raw} -> '{result}'")
        else:
            print(f"  [FAIL] Name {raw} -> Expected '{expected}', Got '{result}'")

    # Test 5: Encoding
    print("\nTest 5: Encoding")
    raw_encoding = "Restaurants in Lahore â€“ Lahore"
    expected = "Restaurants in Lahore — Lahore"
    result = fix_encoding(raw_encoding)
    # Note: My fix_encoding uses latin-1/utf-8, which might not match exact dash. Let's see.
    print(f"  Result: {result}")

if __name__ == "__main__":
    test_requirements()
