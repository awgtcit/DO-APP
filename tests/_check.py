import requests, re

s = requests.Session()
s.post("http://127.0.0.1:5080/auth/login", data={"username": "sathish.narasimhan", "password": "Malt*2025"})

for name, path in [
    ("Dashboard", "/"),
    ("IT Support List", "/it-support/"),
    ("IT Support Create", "/it-support/create"),
    ("CSS", "/static/css/app.css"),
    ("JS", "/static/js/app.js"),
]:
    r = s.get(f"http://127.0.0.1:5080{path}")
    print(f"{name}: {r.status_code} len={len(r.text)}")

r = s.get("http://127.0.0.1:5080/it-support/")
matches = re.findall(r'stat-card__value">(.*?)<', r.text)
print("IT Stats:", matches)
