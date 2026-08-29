#!/usr/bin/env python3
"""Test exact agent query for G01-018."""
import json
from urllib.request import Request, urlopen, HTTPError
from urllib.parse import urlencode

env_path = '/workspace/secrets/collector.env'
values = {}
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        values[k.strip()] = v.strip().strip("'\"")

token_url = 'https://login.microsoftonline.com/{}/oauth2/v2.0/token'.format(values['GRAPH_TENANT_ID'])
body = urlencode({
    'grant_type': 'client_credentials',
    'client_id': values['GRAPH_CLIENT_ID'],
    'client_secret': values['GRAPH_CLIENT_SECRET'],
    'scope': 'https://graph.microsoft.com/.default'
}).encode('ascii')
req = Request(token_url, data=body, headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
with urlopen(req, timeout=30) as resp:
    token = json.loads(resp.read().decode('utf-8'))['access_token']

# Exact agent query as built by _endpoint_url for G01-018
select = ["id", "displayName", "isBuiltIn", "isEnabled", "templateId", "version"]
top = 100
query = {"$select": ",".join(select), "$top": str(top)}
url = "https://graph.microsoft.com/v1.0/roleManagement/directory/roleDefinitions?" + urlencode(query)
print("URL:", url)

try:
    req2 = Request(url, headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'})
    with urlopen(req2, timeout=30) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        vals = data.get('value', [])
        print('HTTP 200, rows={}'.format(len(vals)))
except HTTPError as e:
    print('HTTP', e.code)
    print('Body:', e.read().decode('utf-8'))

# Now try with no top (let default page size apply)
print()
print("=== No $top, only $select ===")
query2 = {"$select": ",".join(select)}
url2 = "https://graph.microsoft.com/v1.0/roleManagement/directory/roleDefinitions?" + urlencode(query2)
print("URL:", url2)
try:
    req3 = Request(url2, headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'})
    with urlopen(req3, timeout=30) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        vals = data.get('value', [])
        print('HTTP 200, rows={}'.format(len(vals)))
except HTTPError as e:
    print('HTTP', e.code)
    print('Body:', e.read().decode('utf-8'))

# Try with $top=20
print()
print("=== $top=20 ===")
query3 = {"$select": ",".join(select), "$top": "20"}
url3 = "https://graph.microsoft.com/v1.0/roleManagement/directory/roleDefinitions?" + urlencode(query3)
print("URL:", url3)
try:
    req4 = Request(url3, headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'})
    with urlopen(req4, timeout=30) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        vals = data.get('value', [])
        print('HTTP 200, rows={}'.format(len(vals)))
except HTTPError as e:
    print('HTTP', e.code)
    print('Body:', e.read().decode('utf-8'))