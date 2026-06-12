"""
ASAGUS Mailer - System Test Script
Tests all major components to ensure the system is working correctly
"""

import requests
import time
import sys

BASE_URL = "http://localhost:8000"

def test_health():
    """Test if backend is running"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Backend Health Check: PASSED")
            return True
        else:
            print(f"❌ Backend Health Check: FAILED (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Backend Health Check: FAILED (Error: {e})")
        return False

def test_root():
    """Test root endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Root Endpoint: PASSED (Version: {data.get('version')})")
            return True
        else:
            print(f"❌ Root Endpoint: FAILED")
            return False
    except Exception as e:
        print(f"❌ Root Endpoint: FAILED (Error: {e})")
        return False

def test_senders_list():
    """Test senders list endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/senders", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Senders List: PASSED ({len(data)} senders)")
            return True
        else:
            print(f"❌ Senders List: FAILED")
            return False
    except Exception as e:
        print(f"❌ Senders List: FAILED (Error: {e})")
        return False

def test_leads_files():
    """Test leads files endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/leads/files", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Lead Files: PASSED ({len(data)} files)")
            return True
        else:
            print(f"❌ Lead Files: FAILED")
            return False
    except Exception as e:
        print(f"❌ Lead Files: FAILED (Error: {e})")
        return False

def test_templates():
    """Test templates endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/templates", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Templates: PASSED ({len(data)} templates)")
            return True
        else:
            print(f"❌ Templates: FAILED")
            return False
    except Exception as e:
        print(f"❌ Templates: FAILED (Error: {e})")
        return False

def test_campaigns():
    """Test campaigns endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/campaigns", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Campaigns: PASSED ({len(data)} campaigns)")
            return True
        else:
            print(f"❌ Campaigns: FAILED")
            return False
    except Exception as e:
        print(f"❌ Campaigns: FAILED (Error: {e})")
        return False

def test_analytics_overview():
    """Test analytics overview endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/analytics/overview", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Analytics Overview: PASSED (Sent: {data.get('total_sent', 0)}, Replies: {data.get('total_replies', 0)})")
            return True
        else:
            print(f"❌ Analytics Overview: FAILED")
            return False
    except Exception as e:
        print(f"❌ Analytics Overview: FAILED (Error: {e})")
        return False

def test_replies_stats():
    """Test replies stats endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/replies/stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Replies Stats: PASSED (Unread: {data.get('unread_count', 0)})")
            return True
        else:
            print(f"❌ Replies Stats: FAILED")
            return False
    except Exception as e:
        print(f"❌ Replies Stats: FAILED (Error: {e})")
        return False

def test_followups_stats():
    """Test followups stats endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/followups/stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Followups Stats: PASSED (Pending: {data.get('pending_total', 0)})")
            return True
        else:
            print(f"❌ Followups Stats: FAILED")
            return False
    except Exception as e:
        print(f"❌ Followups Stats: FAILED (Error: {e})")
        return False

def test_warmup_sessions():
    """Test warmup sessions endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/warmup/sessions", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Warmup Sessions: PASSED ({len(data)} sessions)")
            return True
        else:
            print(f"❌ Warmup Sessions: FAILED")
            return False
    except Exception as e:
        print(f"❌ Warmup Sessions: FAILED (Error: {e})")
        return False

def test_database():
    """Test if database file exists"""
    import os
    db_path = "../../asagus.db"
    if os.path.exists(db_path):
        size = os.path.getsize(db_path)
        print(f"✅ Database File: EXISTS ({size} bytes)")
        return True
    else:
        print(f"❌ Database File: NOT FOUND")
        return False

def main():
    print("=" * 60)
    print("ASAGUS MAILER - SYSTEM TEST")
    print("=" * 60)
    print()
    
    print("Waiting for backend to start...")
    time.sleep(2)
    
    tests = [
        ("Health Check", test_health),
        ("Root Endpoint", test_root),
        ("Database File", test_database),
        ("Senders API", test_senders_list),
        ("Leads API", test_leads_files),
        ("Templates API", test_templates),
        ("Campaigns API", test_campaigns),
        ("Analytics API", test_analytics_overview),
        ("Replies API", test_replies_stats),
        ("Followups API", test_followups_stats),
        ("Warmup API", test_warmup_sessions),
    ]
    
    results = []
    print("\nRunning Tests...")
    print("-" * 60)
    
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))
        time.sleep(0.5)
    
    print()
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\nPassed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! System is working correctly.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
