import requests
import time

print("Testing ASAGUS Mailer Backend...")
print("-" * 50)

# Wait a bit for server to start
time.sleep(2)

tests = {
    "Health Check": "http://localhost:8000/health",
    "Root Endpoint": "http://localhost:8000/",
    "Senders API": "http://localhost:8000/api/senders",
    "Templates API": "http://localhost:8000/api/templates",
    "Campaigns API": "http://localhost:8000/api/campaigns",
    "Analytics": "http://localhost:8000/api/analytics/overview",
}

passed = 0
failed = 0

for name, url in tests.items():
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"✓ {name}: OK")
            passed += 1
        else:
            print(f"✗ {name}: FAILED (Status {response.status_code})")
            failed += 1
    except Exception as e:
        print(f"✗ {name}: ERROR ({str(e)[:50]})")
        failed += 1

print("-" * 50)
print(f"Results: {passed} passed, {failed} failed")

if failed == 0:
    print("\n✓ All tests passed! Backend is working correctly.")
else:
    print(f"\n✗ {failed} test(s) failed. Check the backend logs.")
