"""Diagnose what happens to URLs in offline mode — why records=0."""
import json
import time
import urllib.request
from collections import Counter

BASE = "http://localhost:8000"

payload = json.dumps({"query": "restaurants", "location": "Lahore", "limit": 5, "mode": "fast"}).encode()
req = urllib.request.Request(BASE + "/api/jobs", data=payload, headers={"Content-Type": "application/json"}, method="POST")
job = json.loads(urllib.request.urlopen(req).read())
job_id = job["id"]
print("Job:", job_id)

time.sleep(6)
data = json.loads(urllib.request.urlopen(BASE + f"/api/jobs/{job_id}").read())
j = data["job"]
events = data["events"]

print(f"Status: {j['status']}")
print(f"Records found: {j['records_found']}")
print(f"Processed: {j['processed_targets']}")
print(f"Skipped: {j['skipped_targets']}")
print()

counts = Counter(ev["event_type"] for ev in events)
print("Event type counts:")
for k, v in sorted(counts.items()):
    print(f"  {k}: {v}")
print()

print("First 5 skip events:")
skip_events = [ev for ev in events if "skip" in ev["event_type"].lower() or "offline" in ev["event_type"].lower() or "compliance" in ev["event_type"].lower()]
for ev in skip_events[:5]:
    msg = ev["message"][:80]
    print(f"  [{ev['layer']}] {ev['event_type']}: {msg}")
