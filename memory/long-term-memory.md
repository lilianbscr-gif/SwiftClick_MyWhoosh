# Long-Term Memory — Préférences Confirmées

> Mise à jour quand une préférence est répétée ou explicitement confirmée.

---

## Préférences de communication
- **Langue** : français dans les réponses et la documentation
- **Ton** : direct, concis — pas de résumés en fin de réponse
- **Format** : markdown, liens cliquables pour les fichiers ([file.py](file.py))

## Préférences de code
- **Pas de commentaires** sauf si le WHY est non-évident
- **Pas de docstrings multi-lignes**
- **Pas de gestion d'erreur superflue** pour des cas impossibles
- **Pas de features non demandées** — scope strict à la demande

## Environnement technique
- OS : Windows 11 Home 10.0.26200
- Shell : PowerShell 5.1 — pas de `&&`, pas d'opérateurs ternaires, encodage UTF-16 par défaut
- Python : 3.14.5 — packages installés : bleak 3.0.2, pynput 1.8.2, winrt-runtime 3.2.1
- IDE : VSCode avec extension Claude Code (claude-sonnet-4-6)
- Pas de CLI `claude` dans le PATH — Claude Code tourne uniquement en extension VSCode
- La planification automatique passe par **Windows Task Scheduler** (pas LaunchAgent — macOS only)

---

## Architecture BLE Zwift Click — Patterns confirmés

### Activation du protocole
- Toujours écrire `b"RideOn"` sur UUID `00000003-19ca-4651-86e5-fa29dcdd09d1` (write-without-response) juste après connexion BleakClient
- Sans RideOn : device envoie Format C sur UUID 00000102 (inutilisable)
- Avec RideOn : device envoie Format A sur UUID 00000002 — seule source de données utile

### Décodage des boutons (Format A)
```python
# data[0] == 0x23 et len(data) >= 5
mask = data[3]
# 0xFF → idle   0xFD → bouton MINUS (bit1=0)   0xDF → bouton PLUS (bit5=0)
```

### Heartbeat et silence
- Idle toutes les **90 ms** sur UUID 00000002 (pas 1 s comme supposé initialement)
- SILENCE_TIMEOUT = **3 s** (et non 6 s) : 3 s sans rien = device vraiment endormi
- Le BLE reste "connecté" (`client.is_connected = True`, RSSI excellent) même quand le device dort — ne pas se fier à ces indicateurs pour détecter le sleep

### Debounce multi-appareils
- Ne jamais partager un seul `last_action` entre plusieurs callbacks BLE
- Pattern : `self._last_action = [0.0, 0.0]` indexé par `idx`
- Capturer `idx` dans le closure par valeur : `def notif_cb(_, d, _idx=idx):`

### Batterie BLE
- UUID standard : `00002a19-0000-1000-8000-00805f9b34fb` (Battery Service 0x180F)
- Lire avec `client.read_gatt_char(BATTERY_UUID)` → `data[0]` = pourcentage 0-100
- Disponible sur le Zwift Click V2 (testé : 80%)

### RSSI en production
- Valeur initiale : `adv_data.rssi` depuis `BleakScanner.discover(return_adv=True)`
- Rafraîchissement pendant connexion : `client.rssi` (bleak 3.x Windows, toutes les 5 s)
- RSSI "Excellent" ne garantit pas que le device envoie des données — voir watchdog silence

---

## Diagnostic BLE — Pattern confirmé

Pour reproduire les conditions de production dans diagnostic.py :
1. Connecter avec BleakClient
2. Envoyer `b"RideOn"` sur UUID 00000003 **avant** de souscrire aux notifications
3. Souscrire uniquement à 00000002 pour les données boutons (les autres UUIDs sont bruit)
4. L'UUID 00002a05 lève toujours "Access Denied" — normal, ignorer

---

## Architecture UI tkinter + asyncio

- tkinter ne supporte pas les appels depuis un thread non-main → tout passer par `widget.after(0, fn)`
- Pattern validé : asyncio loop dans thread daemon + `self._ui(fn, *args)` = `self.after(0, fn, *args)`
- Pour mettre à jour un label sans redessiner le canvas : méthode `_update_status(idx, text, color)` séparée de `_refresh_canvas`

---

## Comportements à éviter

- **Ne pas envoyer `0x04 0x00...` comme activation** sur les UUIDs Zwift — c'est un format de test qui change le mode du device
- **Ne pas supposer que `client.is_connected = True` = device actif** — le sleep endort les notifications sans couper la connexion BLE
- **Ne pas partager de timer debounce entre deux appareils BLE distincts**
- **Ne pas utiliser des scripts PowerShell avec des caractères accentués** dans les littéraux de chaînes — PS 5.1 + UTF-8 = problèmes d'encodage. Utiliser l'ASCII pur dans les scripts .ps1

---

## Veille technologique — Fichiers de référence

- `memory/new_learning.md` — trouvailles scorées 1-5, statut nouveau/promu/ignoré
- `scripts/research_scout.py` — scrape HN Algolia + GitHub + PyPI (Reddit bloqué sans auth)
- `scripts/research_review.py` — promotion score ≥ 4 vers ce fichier (dimanche)
- `.claude/commands/skills/research-scout.md` — skill interactif `/skills/research-scout`
- `.claude/commands/skills/research-review.md` — skill interactif `/skills/research-review`
