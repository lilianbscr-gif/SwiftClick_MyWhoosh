"""
logger.py — Enregistrement structuré de tous les événements BLE et boutons.
Fichier de sortie : logs/events_YYYYMMDD_HHMMSS.jsonl (une ligne JSON par événement).
Utilisé pour le debug et pour alimenter les tests unitaires de non-régression.
"""
import json
import threading
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / "logs"


class EventLogger:
    """Logger thread-safe. Écrit en JSONL et maintient un buffer in-memory pour les tests."""

    def __init__(self, enabled: bool = True):
        self._enabled = enabled
        self._lock    = threading.Lock()
        self._buffer: list[dict] = []
        self._path: Path | None  = None

        if enabled:
            LOG_DIR.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._path = LOG_DIR / f"events_{ts}.jsonl"

    # ── Cycle de vie BLE ────────────────────────────────────────

    def connect(self, idx: int, addr: str):
        self._write("connect", idx=idx, addr=addr)

    def ready(self, idx: int, addr: str):
        """Connexion complète — ready=True, boutons actifs."""
        self._write("ready", idx=idx, addr=addr)

    def disconnect(self, idx: int, addr: str, reason: str):
        """reason : 'led_sleep' | 'write_failed' | 'ble_dropped' | 'stop'"""
        self._write("disconnect", idx=idx, addr=addr, reason=reason)

    def reconnect_trigger(self, idx: int, addr: str, silence_s: float):
        """Reconnexion forcée déclenchée."""
        self._write("reconnect_trigger", idx=idx, addr=addr, silence_s=round(silence_s, 2))

    # ── Données BLE brutes ──────────────────────────────────────

    def ble_raw(self, idx: int, uuid_short: str, data: bytearray, ready: bool):
        """Toute notification reçue, avec indicateur ready."""
        self._write("ble_raw",
                    idx=idx, uuid=uuid_short,
                    hex=data.hex(), len=len(data), ready=ready)

    # ── État boutons ────────────────────────────────────────────

    def btn_fire(self, idx: int, key: str, label: str, mask: int, addr: str = ""):
        self._write("btn_fire", idx=idx, addr=addr, key=key, label=label, mask=f"0x{mask:02X}")

    def btn_block(self, idx: int, reason: str, mask: int, addr: str = ""):
        """reason : 'state_machine' | 'debounce' | 'cross_debounce' | 'not_ready'"""
        self._write("btn_block", idx=idx, addr=addr, reason=reason, mask=f"0x{mask:02X}")

    def btn_release(self, idx: int, addr: str = ""):
        """mask=0xFF reçu — bouton relâché."""
        self._write("btn_release", idx=idx, addr=addr)

    # ── Silence / LED ───────────────────────────────────────────

    def led_warn(self, idx: int, addr: str, silence_s: float):
        """Silence > SILENCE_WARN — LED probablement éteinte."""
        self._write("led_warn", idx=idx, addr=addr, silence_s=round(silence_s, 2))

    # ── Accès buffer pour tests ──────────────────────────────────

    def events(self, ev_type: str | None = None) -> list[dict]:
        with self._lock:
            if ev_type is None:
                return list(self._buffer)
            return [e for e in self._buffer if e["ev"] == ev_type]

    def count(self, ev_type: str) -> int:
        return len(self.events(ev_type))

    def clear(self):
        with self._lock:
            self._buffer.clear()

    # ── Interne ──────────────────────────────────────────────────

    def _write(self, ev: str, **kwargs):
        row = {"t": datetime.now().strftime("%H:%M:%S.%f")[:-3], "ev": ev, **kwargs}
        with self._lock:
            self._buffer.append(row)
            if self._path:
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
