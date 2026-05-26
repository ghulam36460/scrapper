"""End-to-end API job test — submits a real job and polls until complete."""
import json
import sys
import time
import urllib.request

BASE = "http://localhost:8000"

payload = json.dumps({
    "query": "restaurants",
    "location": "Lahore",
    "limit": 10,
    "mode": "balanced",
}).encode()

req = urllib.request.Request(
    BASE + "/api/jobs",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
resp = urllib.request.urlopen(req)
job = json.loads(resp.read())
job_id = job["id"]
print(f"Job started: {job_id}")
print(f"Initial status: {job['status']}")
print()

for attempt in range(20):
    time.sleep(2)
    r = urllib.request.urlopen(BASE + f"/api/jobs/{job_id}")
    data = json.loads(r.read())
    j = data["job"]
    print(
        f"  [{attempt+1:02d}] status={j['status']:<12} "
        f"records={j['records_found']}/{10}  "
        f"processed={j['processed_targets']}  "
        f"skipped={j['skipped_targets']}  "
        f"msg={j['progress_message'][:50]!r}"
    )
    if j["status"] in ("completed", "failed", "cancelled"):
        print()
        if j["status"] == "failed":
            print(f"FAILED: {j['error']}")
            sys.exit(1)
        else:
            print(f"COMPLETED: {j['records_found']} records stored")
        print()
        print("Last 8 events:")
        for ev in data["events"][:8]:
            print(f"  [{ev['layer']:15}] {ev['event_type']:30} {ev['message'][:60]}")
        break
else:
    print("TIMEOUT: job did not finish in 40 seconds")
