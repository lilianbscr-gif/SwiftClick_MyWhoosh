#!/usr/bin/env python3
"""Test rapide de connectivite aux APIs utilisees par research_scout."""
import json
import ssl
import urllib.request

ctx = ssl.create_default_context()

def fetch(url):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "SwiftClick-test/1.0")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=12, context=ctx) as r:
        return json.loads(r.read())

print("Test HackerNews Algolia...")
data = fetch("https://hn.algolia.com/api/v1/search?query=python+bleak+bluetooth&tags=story&hitsPerPage=3")
hits = data.get("hits", [])
print(f"  OK — {len(hits)} resultats")
for h in hits[:2]:
    print(f"    - {h['title'][:70]}")

print("\nTest GitHub API...")
data = fetch("https://api.github.com/search/repositories?q=bleak+windows+python+language:python&sort=updated&per_page=3")
items = data.get("items", [])
print(f"  OK — {len(items)} resultats")
for i in items[:2]:
    print(f"    - {i['full_name']} ({i.get('description','')[:50]})")

print("\nTest Reddit JSON...")
req = urllib.request.Request(
    "https://www.reddit.com/r/Python/search.json?q=bleak+bluetooth&sort=new&limit=3&t=month"
)
req.add_header("User-Agent", "SwiftClick-test/1.0 (research bot)")
with urllib.request.urlopen(req, timeout=12, context=ctx) as r:
    data = json.loads(r.read())
posts = data.get("data", {}).get("children", [])
print(f"  OK — {len(posts)} resultats")
for p in posts[:2]:
    print(f"    - {p['data']['title'][:70]}")

print("\nToutes les APIs sont accessibles.")
