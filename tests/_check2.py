import requests, re

s = requests.Session()
s.post("http://127.0.0.1:5080/auth/login", data={"username": "sathish.narasimhan", "password": "Malt*2025"})

r = s.get("http://127.0.0.1:5080/it-support/")
# Extract the traceback from the flask debug page
text = r.text
# Find the traceback text
tb_match = re.search(r'<div class="traceback">(.*?)</div>', text, re.DOTALL)
if tb_match:
    import html
    print(html.unescape(re.sub(r'<[^>]+>', '', tb_match.group(1)))[:3000])
else:
    # Try pre tags
    pre_matches = re.findall(r'<pre[^>]*>(.*?)</pre>', text, re.DOTALL)
    for m in pre_matches[-3:]:
        print(re.sub(r'<[^>]+>', '', m)[:1000])
        print("---")
