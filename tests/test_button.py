"""
test_button.py — Tests unitaires de non-régression pour la logique boutons.

Séquences BLE issues des diagnostics réels sur les deux Swift Click V2.
Architecture : mapping par masque BLE (comme bikecontrol/OpenBikeControl).
  0xDF (bit 5 = 0 → bit 12 buttonMap = SHFT_UP_R) = TOUCHE_PLUS
  0xFD (bit 1 = 0 → bit 8  buttonMap = SHFT_UP_L) = TOUCHE_MOINS
"""
import time
import threading
import pytest

from tests.conftest import replay
from tests.fixtures.sequences import (
    PLUS_SINGLE_TAP, PLUS_DOUBLE_TAP, PLUS_HOLD, PLUS_RACE,
    MINUS_SINGLE_TAP, MINUS_DOUBLE_TAP,
    MINUS_AFTER_RECONNECT, INIT_BURST,
)
import interface as m


# ── Bouton PLUS (mask=0xDF) ───────────────────────────────────────────────────

class TestPlusButton:

    def test_single_tap_fires_once(self, app):
        """1 tap physique = 2 notifications BLE = 1 seule commande."""
        app._btn_pressed[0] = False
        app._last_fire[0]   = 0.0
        fires = replay(app, PLUS_SINGLE_TAP, idx=0)
        assert fires == 1, f"Attendu 1, obtenu {fires} (pattern 0xDF×2 → 0xFF)"

    def test_hold_fires_once(self, app):
        """Maintien du bouton pendant ~2s → 1 seule commande."""
        app._btn_pressed[0] = False
        app._last_fire[0]   = 0.0
        fires = replay(app, PLUS_HOLD, idx=0)
        assert fires == 1, f"Maintien : attendu 1, obtenu {fires}"

    def test_double_tap_fires_twice(self, app):
        """2 taps physiques séparés de 500ms → 2 commandes."""
        app._btn_pressed[0] = False
        app._last_fire[0]   = 0.0
        fires = replay(app, PLUS_DOUBLE_TAP, idx=0)
        assert fires == 2, f"Double tap : attendu 2, obtenu {fires}"

    def test_race_condition_fires_once(self, app):
        """Race condition : 2 threads simultanés → 1 seule commande (lock atomique)."""
        app._btn_pressed[0] = False
        app._last_fire[0]   = 0.0
        fires = replay(app, PLUS_RACE, idx=0, concurrent=True)
        assert fires == 1, f"Race condition : attendu 1, obtenu {fires}"

    def test_debounce_blocks_rapid_retrigger(self, app):
        """Pattern 0xDF→0xFF→0xDF dans <150ms → 1 seule commande (debounce)."""
        D = bytearray.fromhex("2308ffdfffff0f")
        I = bytearray.fromhex("2308ffffffff0f")
        app._btn_pressed[0]  = False
        app._last_fire[0]    = 0.0
        app._last_key_fired  = None

        app._on_data(D, 0)   # feu
        app._on_data(I, 0)   # idle → btn_pressed=False
        app._on_data(D, 0)   # <150ms → bloqué par debounce

        fires = len([e for e in app.keyboard_presses if e[0] == "press"])
        assert fires == 1, f"Debounce : attendu 1, obtenu {fires}"

    def test_key_is_touche_plus(self, app):
        """mask=0xDF → TOUCHE_PLUS (protocole bikecontrol)."""
        D = bytearray.fromhex("2308ffdfffff0f")
        app._btn_pressed[0]  = False
        app._last_fire[0]    = 0.0
        app._last_key_fired  = None
        app._on_data(D, 0)
        presses = [e[1] for e in app.keyboard_presses if e[0] == "press"]
        assert presses == [m.TOUCHE_PLUS], f"Attendu TOUCHE_PLUS, obtenu {presses}"

    def test_mask_not_idx_determines_key(self, app):
        """mask=0xDF → TOUCHE_PLUS quel que soit idx (mapping par masque, pas idx)."""
        D = bytearray.fromhex("2308ffdfffff0f")
        for idx in (0, 1):
            app._btn_pressed[idx] = False
            app._last_fire[idx]   = 0.0
            app._global_key       = None   # reset dedup entre les deux devices
            app.keyboard_presses.clear()
            app._on_data(D, idx)
            presses = [e[1] for e in app.keyboard_presses if e[0] == "press"]
            assert presses == [m.TOUCHE_PLUS], f"idx={idx}, mask=0xDF doit → TOUCHE_PLUS"


# ── Bouton MINUS (mask=0xFD) ──────────────────────────────────────────────────

class TestMinusButton:

    def test_single_tap_fires_once(self, app):
        """1 tap physique sur minus → 1 commande."""
        app._btn_pressed[1] = False
        app._last_fire[1]   = 0.0
        fires = replay(app, MINUS_SINGLE_TAP, idx=1)
        assert fires == 1, f"Minus tap : attendu 1, obtenu {fires}"

    def test_double_tap_fires_twice(self, app):
        """2 taps minus → 2 commandes."""
        app._btn_pressed[1] = False
        app._last_fire[1]   = 0.0
        fires = replay(app, MINUS_DOUBLE_TAP, idx=1)
        assert fires == 2, f"Minus double tap : attendu 2, obtenu {fires}"

    def test_key_is_touche_moins(self, app):
        """mask=0xFD → TOUCHE_MOINS (protocole bikecontrol)."""
        D = bytearray.fromhex("2308fffdffff0f")
        app._btn_pressed[1]  = False
        app._last_fire[1]    = 0.0
        app._last_key_fired  = None
        app._on_data(D, 1)
        presses = [e[1] for e in app.keyboard_presses if e[0] == "press"]
        assert presses == [m.TOUCHE_MOINS], f"Attendu TOUCHE_MOINS, obtenu {presses}"

    def test_mask_fd_gives_moins_on_any_idx(self, app):
        """mask=0xFD → TOUCHE_MOINS quel que soit idx."""
        D = bytearray.fromhex("2308fffdffff0f")
        for idx in (0, 1):
            app._btn_pressed[idx] = False
            app._last_fire[idx]   = 0.0
            app._global_key       = None   # reset dedup entre les deux devices
            app.keyboard_presses.clear()
            app._on_data(D, idx)
            presses = [e[1] for e in app.keyboard_presses if e[0] == "press"]
            assert presses == [m.TOUCHE_MOINS], f"idx={idx}, mask=0xFD doit → TOUCHE_MOINS"

    def test_fires_after_reconnect(self, app):
        """Après reconnexion (reset état), minus doit répondre immédiatement."""
        app._btn_pressed[1] = False
        app._last_fire[1]   = 0.0
        fires = replay(app, MINUS_AFTER_RECONNECT, idx=1)
        assert fires == 1, (
            f"Post-reconnexion : attendu 1 fire, obtenu {fires}."
        )


# ── Déduplication globale (approche bikecontrol _lastButtonsClicked) ─────────

class TestGlobalDedup:

    def test_interference_blocked_until_real_release(self, app):
        """Bug du double-fire : device 1 tire 0xDF, device 0 aussi (interférence).
        Après 100ms, device 0 ne doit PAS retirer même si sa fenêtre est expirée.
        Fix : global_dedup met btn_pressed[0]=True → state_machine bloque ensuite."""
        D   = bytearray.fromhex("2308ffdfffff0f")  # 0xDF → PLUS
        Rel = bytearray.fromhex("2308ffffffff0f")  # 0xFF → idle
        app._btn_pressed = [False, False]
        app._last_fire   = [0.0, 0.0]
        app._global_key  = None

        app._on_data(D, 1)    # 1C:7E fire PLUS → global_key=PLUS, btn_pressed[1]=True
        app._on_data(D, 0)    # AC:08 interference → global_dedup bloque, btn_pressed[0]=True
        app._on_data(D, 0)    # AC:08 encore (90ms après) → state_machine bloque (btn_pressed[0]=True)
        app._on_data(D, 1)    # 1C:7E encore → state_machine bloque (btn_pressed[1]=True)
        app._on_data(D, 0)    # AC:08 à 177ms → state_machine bloque (btn_pressed[0]=True) ← LE FIX

        fires = len([e for e in app.keyboard_presses if e[0] == "press"])
        assert fires == 1, f"Double-fire bug : attendu 1, obtenu {fires}"

    def test_global_key_clears_on_full_release(self, app):
        """global_key se remet à None seulement quand les deux devices ont envoyé 0xFF."""
        D   = bytearray.fromhex("2308ffdfffff0f")
        Rel = bytearray.fromhex("2308ffffffff0f")
        app._btn_pressed = [False, False]
        app._last_fire   = [0.0, 0.0]
        app._global_key  = None

        app._on_data(D, 0)     # device 0 fire, global_key=PLUS
        app._on_data(D, 1)     # device 1 bloqué (global_dedup), btn_pressed[1]=True
        app._on_data(Rel, 0)   # device 0 release → btn_pressed[0]=False, btn_pressed[1]=True → global_key reste PLUS
        assert app._global_key == m.TOUCHE_PLUS, "global_key doit rester PLUS tant que device 1 presse"
        app._on_data(Rel, 1)   # device 1 release → btn_pressed[1]=False, not any → global_key=None
        assert app._global_key is None, "global_key doit être None après release total"

    def test_different_keys_both_fire(self, app):
        """PLUS puis MINUS avec global release entre les deux → les deux tirent."""
        D_plus  = bytearray.fromhex("2308ffdfffff0f")
        D_minus = bytearray.fromhex("2308fffdffff0f")
        Rel     = bytearray.fromhex("2308ffffffff0f")
        app._btn_pressed = [False, False]
        app._last_fire   = [0.0, 0.0]
        app._global_key  = None

        app._on_data(D_plus,  0)    # PLUS → fire
        app._on_data(Rel,     0)    # release → global_key=None
        app._last_fire[1] = 0.0     # reset debounce
        app._on_data(D_minus, 1)    # MINUS → fire (global_key est None)

        presses = [e[1] for e in app.keyboard_presses if e[0] == "press"]
        assert m.TOUCHE_PLUS  in presses, "TOUCHE_PLUS attendu"
        assert m.TOUCHE_MOINS in presses, "TOUCHE_MOINS attendu"
        assert len(presses) == 2, f"Attendu 2 presses, obtenu {len(presses)}"

    def test_race_condition_same_key(self, app):
        """Race condition : 2 threads simultanés avec même touche → 1 seul fire."""
        D = bytearray.fromhex("2308ffdfffff0f")
        app._btn_pressed = [False, False]
        app._last_fire   = [0.0, 0.0]
        app._global_key  = None

        barrier = threading.Barrier(2)

        def call(idx):
            barrier.wait()
            app._on_data(D, idx)

        t1 = threading.Thread(target=call, args=(0,))
        t2 = threading.Thread(target=call, args=(1,))
        t1.start(); t2.start()
        t1.join();  t2.join()

        fires = len([e for e in app.keyboard_presses if e[0] == "press"])
        assert fires == 1, f"Race condition same-key : attendu 1 fire, obtenu {fires}"


# ── Non-régression : données filtrées ────────────────────────────────────────

class TestDataFiltering:

    @pytest.mark.parametrize("hex_data,desc", [
        ("191050",         "heartbeat 25 16 80 (non Format-A)"),
        ("0105",           "Format C pre-RideOn (2 octets, 0x01)"),
        ("0405",           "Format C release pre-RideOn"),
        ("2308ffffffff0f", "idle mask=0xFF"),
        ("23",             "trop court (1 octet)"),
        ("2300",           "trop court (2 octets)"),
    ])
    def test_non_button_data_ignored(self, app, hex_data, desc):
        """Toutes les trames non-bouton doivent être ignorées sans fire."""
        app._btn_pressed[0]  = False
        app._last_fire[0]    = 0.0
        app._last_key_fired  = None
        app._on_data(bytearray.fromhex(hex_data), 0)
        presses = [e for e in app.keyboard_presses if e[0] == "press"]
        assert len(presses) == 0, f"'{desc}' ne doit pas tirer"

    def test_unknown_mask_ignored(self, app):
        """Masque inconnu (ni 0xDF ni 0xFD ni 0xFF) → ignoré."""
        data = bytearray.fromhex("2308ffefffff0f")  # mask=0xEF
        app._btn_pressed[0]  = False
        app._last_fire[0]    = 0.0
        app._last_key_fired  = None
        app._on_data(data, 0)
        presses = [e for e in app.keyboard_presses if e[0] == "press"]
        assert len(presses) == 0, "Masque inconnu ne doit pas tirer"
