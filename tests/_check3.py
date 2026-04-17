import requests, re, html as htmlmod

s = requests.Session()
s.post("http://127.0.0.1:5080/auth/login", data={"username": "sathish.narasimhan", "password": "Malt*2025"})

r = s.get("http://127.0.0.1:5080/it-support/")
text = r.text
# Find the actual error class/message - flask debug pages have class="errormsg"
err = re.search(r'class="errormsg">(.*?)</pre>', text, re.DOTALL)
if err:
    print("ERROR:", htmlmod.unescape(re.sub(r'<[^>]+>', '', err.group(1)))[:2000])
# Also look for the exception line
exc = re.findall(r'<h1>(.*?)</h1>', text)
for e in exc:
    print("H1:", htmlmod.unescape(e))
# Look for line with "Error" or "Exception"  
lines = text.split('\n')
for line in lines:
    stripped = re.sub(r'<[^>]+>', '', line).strip()
    if stripped and ('Error' in stripped or 'Exception' in stripped or 'error' in stripped) and len(stripped) < 300:
        print(">>", stripped)
