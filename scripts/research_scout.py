#!/usr/bin/env python3
"""
Research Scout — veille automatisée pour SwiftClick_MyWhoosh.
Sources: HackerNews, GitHub, PyPI releases. Stocke dans memory/new_learning.md.
"""
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
MEMORY_FILE = PROJECT_DIR / "memory" / "new_learning.md"
LOG_FILE = PROJECT_DIR / "logs" / "scout.log"
ENV_FILE = PROJECT_DIR / ".env"

# Charger .env si présent
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
SSL_CTX = ssl.create_default_context()

PROJECT_CONTEXT = """
SwiftClick_MyWhoosh: bridge Python entre un périphérique hardware (clavier/bouton Swift)
et le simulateur de cyclisme indoor MyWhoosh sur Windows 11.
Stack: pynput (simulation clavier/souris), bleak (Bluetooth LE), winrt (Windows Runtime),
Python 3.14. Intérêts: BLE/HID Python Windows, input automation, indoor cycling app
integration (MyWhoosh/Zwift), latence faible, alternatives pynput/bleak, Windows Gaming APIs.
"""

# Requêtes de recherche par source
HN_QUERIES = [
    "python bleak bluetooth windows",
    "python pynput keyboard windows automation",
    "python HID gamepad windows controller",
    "python BLE windows HID 2025",
    "indoor cycling app python automation",
]

# Packages PyPI à surveiller (releases + changelog)
PYPI_PACKAGES = [
    "bleak",
    "pynput",
    "winrt-runtime",
    "inputs",
    "pywinusb",
    "hid",
    "vgamepad",
    "keyboard",
    "mouse",
]

GITHUB_QUERIES = [
    "bleak windows bluetooth python",
    "pynput keyboard windows automation",
    "python virtual-gamepad windows hid",
    "mywhoosh zwift python",
    "python ble hid bridge windows",
]


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def fetch_json(url: str, headers: dict | None = None, timeout: int = 12) -> dict | None:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "SwiftClick-ResearchScout/1.0 (research bot)")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        log(f"  [http {e.code}] {url[:70]}")
    except Exception as e:
        log(f"  [err] {url[:70]} → {type(e).__name__}")
    return None


def search_hn(query: str) -> list[dict]:
    since = int((datetime.now(timezone.utc) - timedelta(days=45)).timestamp())
    url = "https://hn.algolia.com/api/v1/search?" + urllib.parse.urlencode({
        "query": query,
        "tags": "story",
        "hitsPerPage": 6,
        "numericFilters": f"created_at_i>{since}",
    })
    data = fetch_json(url)
    if not data:
        return []
    results = []
    for hit in data.get("hits", []):
        item_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}"
        results.append({
            "title": hit.get("title", "").strip(),
            "url": item_url,
            "source": "HackerNews",
            "date": hit.get("created_at", "")[:10],
            "query": query,
        })
    return results


def search_pypi(package: str) -> list[dict]:
    """Surveille les releases récentes d'un package PyPI."""
    url = f"https://pypi.org/pypi/{package}/json"
    data = fetch_json(url)
    if not data:
        return []
    info = data.get("info", {})
    releases = data.get("releases", {})
    # Trier par version décroissante — prendre les 2 dernières
    versions = sorted(releases.keys(), reverse=True)[:2]
    results = []
    for ver in versions:
        files = releases.get(ver, [])
        if not files:
            continue
        upload_time = files[0].get("upload_time", "")[:10]
        # Ignorer les releases de plus de 90 jours
        try:
            age = (datetime.now() - datetime.fromisoformat(upload_time)).days
            if age > 90:
                continue
        except Exception:
            pass
        summary = info.get("summary", "") or ""
        results.append({
            "title": f"{package} {ver} released — {summary[:80]}",
            "url": f"https://pypi.org/project/{package}/{ver}/",
            "source": f"PyPI/{package}",
            "date": upload_time,
            "query": package,
        })
    return results


def search_github(query: str) -> list[dict]:
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode({
        "q": query + " language:python",
        "sort": "updated",
        "order": "desc",
        "per_page": 5,
    })
    data = fetch_json(url, headers=headers)
    if not data:
        return []
    results = []
    for repo in data.get("items", []):
        desc = (repo.get("description") or "")[:80]
        stars = repo.get("stargazers_count", 0)
        results.append({
            "title": f"{repo['full_name']} ★{stars} — {desc}",
            "url": repo["html_url"],
            "source": "GitHub",
            "date": repo.get("updated_at", "")[:10],
            "query": query,
        })
    return results


def gather_all() -> list[dict]:
    seen_urls: set[str] = set()
    all_items: list[dict] = []

    # Charger les URLs déjà dans new_learning.md pour éviter doublons
    if MEMORY_FILE.exists():
        content = MEMORY_FILE.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.strip().startswith("- **URL**"):
                url = line.split(":", 1)[-1].strip()
                seen_urls.add(url)

    def add(items: list[dict]):
        for item in items:
            if item["url"] and item["url"] not in seen_urls and item["title"]:
                seen_urls.add(item["url"])
                all_items.append(item)

    log("  HackerNews...")
    for q in HN_QUERIES:
        add(search_hn(q))

    log("  GitHub...")
    for q in GITHUB_QUERIES:
        add(search_github(q))

    log("  PyPI releases...")
    for pkg in PYPI_PACKAGES:
        add(search_pypi(pkg))

    return all_items


def score_with_claude(items: list[dict]) -> list[dict]:
    if not API_KEY:
        log("  [info] Pas d'API key — scoring par mots-clés")
        return score_with_keywords(items)

    try:
        import anthropic
    except ImportError:
        import subprocess
        log("  Installation du package anthropic...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "anthropic", "-q"])
        import anthropic

    client = anthropic.Anthropic(api_key=API_KEY)

    # Traiter en lots de 20 pour ne pas dépasser le contexte
    scored: list[dict] = []
    batch_size = 20
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        items_json = json.dumps(
            [{"id": j, "title": r["title"], "source": r["source"]} for j, r in enumerate(batch)],
            ensure_ascii=False,
        )
        prompt = f"""Contexte du projet:
{PROJECT_CONTEXT}

{len(batch)} résultats de veille. Pour chacun, attribue:
- score 1-5 (5=directement applicable, 4=très pertinent, 3=pertinent, 2=indirect, 1=hors sujet)
- summary: résumé 1 ligne en français (max 120 chars)

Réponds UNIQUEMENT avec un JSON valide: liste d'objets {{\"id\":int, \"score\":int, \"summary\":str}}

Résultats:
{items_json}"""

        try:
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            parsed = json.loads(msg.content[0].text)
            for entry in parsed:
                idx = entry["id"]
                batch[idx]["score"] = entry["score"]
                batch[idx]["summary"] = entry["summary"]
            scored.extend(batch)
        except Exception as e:
            log(f"  [warn] Claude API erreur: {e} — fallback keywords")
            scored.extend(score_with_keywords(batch))

    return [r for r in scored if r.get("score", 0) >= 2]


def score_with_keywords(items: list[dict]) -> list[dict]:
    kw_high = {
        "bleak", "pynput", "hid", "bluetooth", "ble", "mywhoosh", "zwift",
        "winrt", "windows runtime", "gamepad", "virtual controller",
    }
    kw_med = {
        "keyboard", "mouse", "input", "automation", "python", "windows",
        "cycling", "indoor", "usb", "device", "controller", "bluetooth",
    }
    for r in items:
        text = (r["title"] + " " + r.get("query", "")).lower()
        score = 1 + min(4, sum(2 for kw in kw_high if kw in text) + sum(1 for kw in kw_med if kw in text))
        r["score"] = min(5, score)
        r["summary"] = r["title"][:120]
    return [r for r in items if r["score"] >= 2]


def write_to_memory(items: list[dict]) -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    items_sorted = sorted(items, key=lambda x: -x.get("score", 0))

    entries = []
    for r in items_sorted:
        score = r.get("score", 1)
        summary = (r.get("summary") or r["title"])[:120]
        entries.append(
            f"\n### [{score}/5] {summary}\n"
            f"- **Source** : {r.get('source', 'web')}\n"
            f"- **URL** : {r.get('url', '')}\n"
            f"- **Trouvé** : {r.get('date', today)} | **Scout** : {today}\n"
            f"- **Statut** : nouveau\n"
        )

    if not entries:
        return 0

    section = f"\n## {today}\n" + "".join(entries)

    if MEMORY_FILE.exists():
        content = MEMORY_FILE.read_text(encoding="utf-8")
    else:
        content = "# New Learning — Veille Technologique\n\n"

    MEMORY_FILE.write_text(content + section, encoding="utf-8")
    return len(entries)


def main():
    log(f"=== Research Scout démarré ===")

    log("Collecte des résultats...")
    raw = gather_all()
    log(f"  {len(raw)} résultats bruts (doublons exclus)")

    if not raw:
        log("Aucun résultat — fin.")
        return

    log("Scoring et résumé...")
    scored = score_with_claude(raw)
    log(f"  {len(scored)} résultats pertinents (score >= 2)")

    count = write_to_memory(scored)
    log(f"  {count} entrées écrites dans memory/new_learning.md")
    log(f"=== Terminé — {count} nouvelles trouvailles ===")


if __name__ == "__main__":
    main()
