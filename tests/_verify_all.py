"""Quick check: login as sathish.narasimhan and hit every route."""
import requests

BASE = "http://127.0.0.1:5080"
s = requests.Session()

# Login
r = s.post(f"{BASE}/auth/login", data={"username": "sathish.narasimhan", "password": "Malt*2025"}, allow_redirects=True)
print(f"Login -> {r.status_code} ({r.url})")

# All routes to check
routes = [
    ("/", "Dashboard"),
    ("/it-support", "IT Support List"),
    ("/it-support/create", "IT Support Create"),
    ("/documents", "Documents (coming soon)"),
    ("/sales-orders", "Sales Orders (coming soon)"),
    ("/announcements", "Announcements (coming soon)"),
    ("/facility", "Facility (coming soon)"),
    ("/users", "Users (coming soon)"),
    ("/settings", "Settings (coming soon)"),
]

all_ok = True
for path, label in routes:
    r = s.get(f"{BASE}{path}")
    status = "OK" if r.status_code == 200 else f"FAIL({r.status_code})"
    if r.status_code != 200:
        all_ok = False
        # Print first 500 chars of error for debugging
        print(f"  {status} {label:35s} {path}")
        # Check if it's a 500 error with traceback
        if r.status_code == 500:
            idx = r.text.find("Traceback")
            if idx >= 0:
                print(f"    Error: {r.text[idx:idx+300]}")
    else:
        print(f"  {status}   {label:35s} {path}")

print(f"\n{'ALL PAGES OK!' if all_ok else 'SOME PAGES FAILED!'}")
