# Recent Memory — Fenêtre Glissante 48h

> Mis à jour par `/consolidate-memory`. Entrées de plus de 48h supprimées automatiquement.

---

## 2026-06-04 — Version stable commitée sur GitHub

### Décisions de session
- Redesign UI complet : palette froide futuriste, cartes octogonales, néon cyan/rose
- Architecture simplifiée : suppression ECDH (non compatible), keepalive bare RideOn 3s
- Race condition BLE résolue : `with self._lock` atomique pour state machine + debounce
- Watchdog silence : `notif_time` mis à jour via keepalive_ack_cb (UUID 00000004)
- Reconnexion forcée supprimée (causait plus de bugs qu'elle n'en résolvait)

### Actions réalisées
- `interface.py` : redesign complet UI + tous les bugs corrigés (double fire, debounce, watchdog)
- `logger.py` : logger JSONL structuré thread-safe
- `zwift_auth.py` : module ECDH (référence, non actif en prod)
- `tests/test_button.py` : 23 tests unitaires — race condition, state machine, debounce, global_dedup
- `scripts/` : research_scout.py + research_review.py + Task Scheduler Windows
- `.gitignore` : créé pour le commit GitHub
- Git installé via winget 2.54.0
- Premier commit GitHub effectué

### Protocole BLE définitivement établi
- UUID 00000004 = canal ack keepalive (device répond RideOn à chaque write)
- Format A sur UUID 00000002 : 0x23 + bitmask (0xDF=PLUS, 0xFD=MINUS, 0xFF=idle)
- `notif_time` doit être mis à jour par les deux callbacks (00000002 ET 00000004)

### Firmware MINUS
- F4:C4:59:03:AC:08 a firmware pré-jan 2025 → LED ne s'allume pas sans MàJ
- Solution : MàJ via app Zwift (à faire)
- F4:C4:59:3F:1C:7E (PLUS) fonctionne parfaitement

---

<!-- Les entrées antérieures à 48h sont supprimées lors du prochain /consolidate-memory -->
