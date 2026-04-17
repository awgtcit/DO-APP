import requests, re, html as htmlmod

s = requests.Session()
s.post("http://127.0.0.1:5080/auth/login", data={"username": "sathish.narasimhan", "password": "Malt*2025"})

# Check if the table exists and get column names
# Use the Flask debug console or just inspect the error more closely

# Let's also check the create page error
r = s.get("http://127.0.0.1:5080/it-support/create")
err = re.search(r'class="errormsg">(.*?)</pre>', r.text, re.DOTALL)
if err:
    print("CREATE ERROR:", htmlmod.unescape(re.sub(r'<[^>]+>', '', err.group(1)))[:2000])
else:
    ti = r.text.find('<title>')
    if ti >= 0:
        print("CREATE TITLE:", r.text[ti+7:r.text.find('</title>')])
    print("CREATE STATUS:", r.status_code)
