"""
Séquences BLE réelles capturées par diagnostic.py sur les deux Swift Click V2.
Utilisées comme fixtures reproductibles pour les tests unitaires.

Format de chaque frame : bytearray(hex_string)
Protocole confirmé : Format A sur UUID 00000002 après activation RideOn.
  data[0]=0x23, data[3]=masque
  0xFF = idle (~90ms)  |  0xDF = BOUTON+  |  0xFD = BOUTON-
"""
from dataclasses import dataclass, field


@dataclass
class BLESequence:
    name: str
    description: str
    frames: list[bytearray]
    delays_ms: list[float]    # délai AVANT chaque frame (index aligné sur frames)
    expected_fires: int
    device: str = "unknown"   # "plus" | "minus"


def _f(hex_str: str) -> bytearray:
    return bytearray.fromhex(hex_str)


# ── Données capturées : Swift Click PLUS (F4:C4:59:3F:1C:7E) ──────────────
# Diagnostic 2026-06-03 : chaque tap physique envoie 2×BOUTON+ avant idle.

PLUS_SINGLE_TAP = BLESequence(
    name="plus_single_tap",
    description="1 tap physique sur + → doit produire exactement 1 commande. "
                "Le device envoie 2 notifications 0xDF en 68ms avant l'idle.",
    device="plus",
    frames=[
        _f("2308ffdfffff0f"),   # BOUTON+ (t=0ms)
        _f("2308ffdfffff0f"),   # BOUTON+ (t=+68ms) — doit être bloqué
        _f("2308ffffffff0f"),   # idle
    ],
    delays_ms=[0, 68, 90],
    expected_fires=1,
)

PLUS_DOUBLE_TAP = BLESequence(
    name="plus_double_tap",
    description="2 taps physiques séparés par >400ms → 2 commandes.",
    device="plus",
    frames=[
        _f("2308ffdfffff0f"),   # tap 1
        _f("2308ffdfffff0f"),   # tap 1 doublon
        _f("2308ffffffff0f"),   # idle
        _f("2308ffffffff0f"),   # idle
        _f("2308ffdfffff0f"),   # tap 2 (>400ms après tap 1)
        _f("2308ffdfffff0f"),   # tap 2 doublon
        _f("2308ffffffff0f"),   # idle
    ],
    delays_ms=[0, 68, 90, 90, 500, 68, 90],  # 500ms entre les deux taps
    expected_fires=2,
)

PLUS_HOLD = BLESequence(
    name="plus_hold",
    description="Maintien du bouton+ pendant ~2s → 1 seule commande.",
    device="plus",
    frames=[_f("2308ffdfffff0f")] * 22 + [_f("2308ffffffff0f")],
    delays_ms=[0] + [90] * 21 + [90],
    expected_fires=1,
)

PLUS_RACE = BLESequence(
    name="plus_race",
    description="2 callbacks simultanés (race condition inter-thread) → 1 seule commande.",
    device="plus",
    frames=[
        _f("2308ffdfffff0f"),   # thread A
        _f("2308ffdfffff0f"),   # thread B simultané
    ],
    delays_ms=[0, 0],           # délai 0 = simultané
    expected_fires=1,
)

# ── Données capturées : Swift Click MINUS (F4:C4:59:03:AC:08) ─────────────
# Diagnostic 2026-06-03 : même pattern 2×BOUTON- avant idle.

MINUS_SINGLE_TAP = BLESequence(
    name="minus_single_tap",
    description="1 tap physique sur - → 1 commande.",
    device="minus",
    frames=[
        _f("2308fffdffff0f"),   # BOUTON-
        _f("2308fffdffff0f"),   # BOUTON- doublon (~90ms)
        _f("2308ffffffff0f"),   # idle
    ],
    delays_ms=[0, 90, 90],
    expected_fires=1,
)

MINUS_DOUBLE_TAP = BLESequence(
    name="minus_double_tap",
    description="2 taps - séparés → 2 commandes.",
    device="minus",
    frames=[
        _f("2308fffdffff0f"),
        _f("2308ffffffff0f"),
        _f("2308fffdffff0f"),   # >400ms après
        _f("2308ffffffff0f"),
    ],
    delays_ms=[0, 90, 500, 90],
    expected_fires=2,
)

# ── Scénario post-reconnexion ─────────────────────────────────────────────
# Vérifie que le device minus envoie correctement des commandes après reconnexion.

MINUS_AFTER_RECONNECT = BLESequence(
    name="minus_after_reconnect",
    description="Premier appui sur minus après une reconnexion → doit tirer. "
                "Vérifie que btn_pressed et last_fire sont bien réinitialisés.",
    device="minus",
    frames=[
        _f("2308ffffffff0f"),   # idle initial (device vient de reconnecter)
        _f("2308ffffffff0f"),   # idle
        _f("2308fffdffff0f"),   # premier appui → DOIT tirer
        _f("2308ffffffff0f"),   # relâché
    ],
    delays_ms=[0, 90, 500, 90],
    expected_fires=1,
)

# ── Données brutes init (avant ready) ─────────────────────────────────────
# Paquets reçus lors de la connexion, avant que ready=True.
# Aucun ne doit déclencher de commande.

INIT_BURST = BLESequence(
    name="init_burst",
    description="Données d'initialisation reçues avant ready=True → 0 commande.",
    device="plus",
    frames=[
        _f("191050"),           # heartbeat 25 16 80 (non-Format-A)
        _f("2308ffffffff0f"),   # idle Format-A
        _f("2308ffdfffff0f"),   # BOUTON+ (ne doit PAS tirer car not ready)
    ],
    delays_ms=[0, 90, 90],
    expected_fires=0,           # ready=False → tout ignoré
)

ALL_SEQUENCES = [
    PLUS_SINGLE_TAP,
    PLUS_DOUBLE_TAP,
    PLUS_HOLD,
    PLUS_RACE,
    MINUS_SINGLE_TAP,
    MINUS_DOUBLE_TAP,
    MINUS_AFTER_RECONNECT,
    INIT_BURST,
]
