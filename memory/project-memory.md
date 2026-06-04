# Project Memory — État Actif des Projets

> Mis à jour manuellement et par `/consolidate-memory`. Reflète l'état courant, pas l'historique.

---

## SwiftClick_MyWhoosh — VERSION STABLE 2026-06-04

**But** : Bridge Python entre deux Zwift Click V2 (BLE) et MyWhoosh sur Windows 11.
Chaque Click envoie une touche clavier (`k` = vitesse+, `i` = vitesse−) via simulation pynput.

**Statut** : **FONCTIONNEL** — les deux Swift Click reconnnus, boutons opérationnels, UI futuriste.

**Répertoire** : `c:\Users\lilia\Documents\SwiftClick_MyWhoosh\`

---

### Fichiers clés
| Fichier | Rôle |
|---|---|
| [interface.py](../interface.py) | Application principale — UI tkinter futuriste + boucle BLE asyncio |
| [logger.py](../logger.py) | Logger structuré JSONL thread-safe |
| [zwift_auth.py](../zwift_auth.py) | Handshake ECDH + keepalive AES-CCM (référence, non utilisé en prod) |
| [diagnostic.py](../diagnostic.py) | Diagnostic BLE brut — envoie RideOn avant souscription |
| [zwift_click_mywhoosh.py](../zwift_click_mywhoosh.py) | Version CLI sans interface |
| [tests/test_button.py](../tests/test_button.py) | 23 tests unitaires de non-régression |
| [scripts/research_scout.py](../scripts/research_scout.py) | Veille automatisée (HN + GitHub + PyPI) |

---

### Protocole BLE Zwift Click V2 — DÉFINITIVEMENT DOCUMENTÉ

**Activation** : `b"RideOn"` sur UUID `00000003-19ca-4651-86e5-fa29dcdd09d1` (write-without-response).
Le device acquitte chaque keepalive avec `b"RideOn"` sur UUID `00000004` (indicate).

**Format A — données boutons et heartbeat (UUID 00000002) :**
- `data[0]=0x23`, bitmask en `data[3]`
- `0xFF` → idle heartbeat (~90ms) — reset notif_time via notif_cb ET keepalive_ack_cb (00000004)
- `0xDF` (bit 5=0) → BOUTON + → TOUCHE_PLUS = `'k'`
- `0xFD` (bit 1=0) → BOUTON − → TOUCHE_MOINS = `'i'`

**Keepalive** : `KEEPALIVE_INTERVAL = 3.0s` (device dort après ~5s sans activité).

**Appareils connus** :
- `F4:C4:59:03:AC:08` — Swift Click MINUS (firmware pré-jan 2025, nécessite MàJ Zwift)
- `F4:C4:59:3F:1C:7E` — Swift Click PLUS (firmware récent, fonctionnel)

---

### Architecture interface.py

**Threading** : asyncio loop dans thread daemon, `_ui(fn)` = `after(0, fn)` thread-safe.

**Logique boutons — 3 couches dans `_on_data`** :
1. State machine par device (`_btn_pressed[idx]`) — front montant uniquement
2. Debounce 50ms par device (`_last_fire[idx]`)
3. Déduplication globale (`_global_key`) — empêche le double fire inter-device
Tout dans `with self._lock:` atomique (race condition BLE threads).

**Silence watchdog** : `notif_time` mis à jour par notif_cb (00000002) ET keepalive_ack_cb (00000004).
- `SILENCE_WARN=5s` → status orange
- Pas de reconnexion forcée (cause des bugs) — `while client.is_connected` gère la déco réelle.

**UI futuriste** : palette `_C` froide, cartes octogonales avec crochets HUD, néon cyan/rose.

---

### Tests — 23 tests unitaires passants
```
python -m pytest tests/test_button.py  # doit rester vert avant tout commit
```

### Tâches actives
- MàJ firmware Swift Click MINUS via l'app Zwift (nécessaire pour activation complète)

### Problèmes connus
- Swift Click MINUS (F4:C4:59:03:AC:08) : LED ne s'allume pas sans MàJ firmware
  → Workaround : les boutons fonctionnent après MàJ firmware Zwift
