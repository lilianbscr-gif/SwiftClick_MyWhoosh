# /skills/research-scout

Veille technologique interactive pour SwiftClick_MyWhoosh.
Scrape Reddit, HackerNews, GitHub — stocke dans `memory/new_learning.md`.

## Contexte projet

SwiftClick_MyWhoosh : bridge Python entre un périphérique hardware (clavier/bouton Swift)
et MyWhoosh (simulateur cyclisme indoor) sur Windows 11.
Stack : **pynput** (simulation clavier/souris), **bleak** (BLE), **winrt** (Windows Runtime), Python 3.14.

Intérêts : BLE/HID Python Windows, input automation, intégration MyWhoosh/Zwift,
latence faible, alternatives/mises à jour pynput et bleak, Windows Gaming APIs.

## Étape 1 — HackerNews (API Algolia)

Fetche chacune de ces URLs et extrais les résultats `hits[]` :

```
https://hn.algolia.com/api/v1/search?query=python+bleak+bluetooth+windows&tags=story&hitsPerPage=5
https://hn.algolia.com/api/v1/search?query=python+pynput+keyboard+windows&tags=story&hitsPerPage=5
https://hn.algolia.com/api/v1/search?query=python+HID+gamepad+windows&tags=story&hitsPerPage=5
https://hn.algolia.com/api/v1/search?query=indoor+cycling+python+automation&tags=story&hitsPerPage=5
https://hn.algolia.com/api/v1/search?query=python+BLE+windows+2025&tags=story&hitsPerPage=5
```

## Étape 2 — Reddit (JSON public)

Fetche avec header `User-Agent: research-bot/1.0` :

```
https://www.reddit.com/r/Python/search.json?q=bleak+bluetooth+windows&sort=new&limit=5&t=month
https://www.reddit.com/r/learnpython/search.json?q=pynput+keyboard+windows&sort=new&limit=5&t=month
https://www.reddit.com/r/Zwift/search.json?q=python+automation+keyboard&sort=new&limit=5&t=month
https://www.reddit.com/r/cycling/search.json?q=MyWhoosh+python&sort=new&limit=5&t=month
https://www.reddit.com/r/homeautomation/search.json?q=python+bluetooth+HID+windows&sort=new&limit=5&t=month
```

## Étape 3 — GitHub (API REST)

Fetche avec header `Accept: application/vnd.github+json` :

```
https://api.github.com/search/repositories?q=bleak+windows+python+language:python&sort=updated&per_page=5
https://api.github.com/search/repositories?q=pynput+keyboard+windows+language:python&sort=updated&per_page=5
https://api.github.com/search/repositories?q=python+virtual-gamepad+windows+language:python&sort=updated&per_page=5
https://api.github.com/search/repositories?q=mywhoosh+zwift+python+language:python&sort=updated&per_page=5
```

## Étape 4 — Déduplication et scoring

Pour chaque résultat :
1. Vérifie que l'URL n'existe pas déjà dans `memory/new_learning.md` (lire le fichier d'abord)
2. Attribue un score 1–5 :
   - **5** : directement applicable (update bleak/pynput, fix BLE Windows, API MyWhoosh)
   - **4** : très pertinent (meilleure pratique BLE/HID, outil input Windows, perf Python)
   - **3** : pertinent indirect (Python updates, Windows APIs généraux, Zwift intégration)
   - **2** : faiblement pertinent (Python général autre OS, autre app cyclisme)
   - **1** : hors sujet — **exclure**
3. Ne garder que score >= 2, max 20 entrées par run

## Étape 5 — Écriture dans new_learning.md

Lis `memory/new_learning.md`, puis ajoute en bas :

```markdown
## YYYY-MM-DD

### [N/5] Résumé d'une ligne en français (max 120 chars)
- **Source** : Reddit/r/Python | HackerNews | GitHub
- **URL** : https://...
- **Trouvé** : YYYY-MM-DD | **Scout** : YYYY-MM-DD (aujourd'hui)
- **Statut** : nouveau
```

## Rapport final

Termine avec :
```
Scout terminé : X entrées ajoutées, Y doublons ignorés, Z sources interrogées.
Prochaine promotion dimanche via /skills/research-review.
```
