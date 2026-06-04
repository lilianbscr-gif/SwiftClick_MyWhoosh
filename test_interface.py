"""
test_interface.py — Tests unitaires de interface.py
Exécution : python -m pytest test_interface.py -v
             python test_interface.py
"""

import sys
import threading
import time
import unittest
from unittest.mock import MagicMock

# ── Mock pynput uniquement (tkinter est disponible nativement sur Windows) ───
_mock_kb = MagicMock()
_mock_kb.Controller = MagicMock       # Controller() retournera un MagicMock
_mock_kb.Key        = MagicMock()
sys.modules.setdefault("pynput",          MagicMock())
sys.modules.setdefault("pynput.keyboard", _mock_kb)

import interface   # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_app():
    """Instance App minimale sans display tkinter.

    On bypasse App.__init__ (qui ouvre une fenêtre) et on câble
    uniquement les attributs nécessaires aux méthodes testées.
    """
    app = object.__new__(interface.App)
    app._last_action = 0.0
    app._lock        = threading.Lock()
    app._count       = 0
    app._count_var   = MagicMock()
    app._last_lbl    = MagicMock()
    # _ui appelle fn(*args) directement (pas de thread tkinter en test)
    app._ui          = lambda fn, *a, **kw: fn(*a, **kw)
    return app


def _packet(mask: int) -> bytearray:
    """Paquet 0x23 valide de 7 octets avec le masque donné."""
    return bytearray([0x23, 0x08, 0xFF, mask, 0xFF, 0xFF, 0x0F])


# ── Tests : detect_key (logique pure, sans App) ───────────────────────────────

class TestDetectKey(unittest.TestCase):
    """detect_key : parsing BLE → touche ou None."""

    def test_plus(self):
        """mask=0xDF (bit 5 à 0) → TOUCHE_PLUS."""
        self.assertEqual(interface.detect_key(_packet(0xDF)), interface.TOUCHE_PLUS)

    def test_moins(self):
        """mask=0xFD (bit 1 à 0) → TOUCHE_MOINS."""
        self.assertEqual(interface.detect_key(_packet(0xFD)), interface.TOUCHE_MOINS)

    def test_idle_mask_ff(self):
        """mask=0xFF → None (idle)."""
        self.assertIsNone(interface.detect_key(_packet(0xFF)))

    def test_header_incorrect(self):
        """data[0] != 0x23 → None."""
        self.assertIsNone(interface.detect_key(
            bytearray([0x15, 0x08, 0xFF, 0xDF, 0xFF, 0xFF, 0x0F])))

    def test_paquet_trop_court(self):
        """len < 5 → None."""
        self.assertIsNone(interface.detect_key(bytearray([0x23, 0x08, 0xFF, 0xDF])))

    def test_paquet_vide(self):
        """bytearray vide → None."""
        self.assertIsNone(interface.detect_key(bytearray()))

    def test_mask_sans_bouton_connu(self):
        """Bits 0x20 et 0x02 tous les deux à 1 → None."""
        # 0b11100011 : bit5=1, bit1=1
        self.assertIsNone(interface.detect_key(_packet(0xE3)))

    def test_les_deux_bits_a_zero(self):
        """Bits 0x20 ET 0x02 clears → priorité donnée au bouton +."""
        # Quand les deux bits sont à 0, 0x20 est testé en premier
        self.assertEqual(interface.detect_key(_packet(0xDC)), interface.TOUCHE_PLUS)


# ── Tests : _on_data (interaction App + clavier) ──────────────────────────────

class TestOnDataRouting(unittest.TestCase):
    """_on_data : routing complet, envoi clavier, compteur."""

    def setUp(self):
        self.app = _make_app()
        interface.keyboard.reset_mock()

    def test_bouton_plus_envoie_k(self):
        self.app._on_data(_packet(0xDF))
        interface.keyboard.press.assert_called_once_with("k")
        interface.keyboard.release.assert_called_once_with("k")

    def test_bouton_moins_envoie_i(self):
        self.app._on_data(_packet(0xFD))
        interface.keyboard.press.assert_called_once_with("i")
        interface.keyboard.release.assert_called_once_with("i")

    def test_press_incremente_compteur(self):
        self.app._on_data(_packet(0xDF))
        self.assertEqual(self.app._count, 1)

    def test_label_vitesse_plus(self):
        self.app._on_data(_packet(0xDF))
        self.app._last_lbl.configure.assert_called_with(text="▲  Vitesse +")

    def test_label_vitesse_moins(self):
        self.app._on_data(_packet(0xFD))
        self.app._last_lbl.configure.assert_called_with(text="▼  Vitesse −")

    def test_mask_idle_ignore(self):
        self.app._on_data(_packet(0xFF))
        interface.keyboard.press.assert_not_called()

    def test_header_incorrect_ignore(self):
        self.app._on_data(bytearray([0x15, 0x08, 0xFF, 0xDF, 0xFF, 0xFF, 0x0F]))
        interface.keyboard.press.assert_not_called()

    def test_paquet_trop_court_ignore(self):
        self.app._on_data(bytearray([0x23, 0x08, 0xFF, 0xDF]))
        interface.keyboard.press.assert_not_called()

    def test_paquet_vide_ignore(self):
        self.app._on_data(bytearray())
        interface.keyboard.press.assert_not_called()


# ── Tests : debounce ──────────────────────────────────────────────────────────

class TestDebounce(unittest.TestCase):

    def setUp(self):
        self.app = _make_app()
        interface.keyboard.reset_mock()

    def test_double_appui_rapide_bloque(self):
        """Deux appuis < DEBOUNCE → un seul envoi."""
        self.app._on_data(_packet(0xDF))
        self.app._on_data(_packet(0xDF))
        interface.keyboard.press.assert_called_once_with("k")

    def test_appui_apres_debounce_accepte(self):
        """Appui après expiration du debounce → deux envois."""
        self.app._on_data(_packet(0xDF))
        self.app._last_action -= interface.DEBOUNCE + 0.1   # simuler l'expiration
        self.app._on_data(_packet(0xDF))
        self.assertEqual(interface.keyboard.press.call_count, 2)

    def test_appui_bloque_ne_compte_pas(self):
        """Appui bloqué par debounce → compteur reste à 1."""
        self.app._on_data(_packet(0xDF))
        self.app._on_data(_packet(0xDF))
        self.assertEqual(self.app._count, 1)


# ── Tests : est_click ─────────────────────────────────────────────────────────

class TestEstClick(unittest.TestCase):

    def _device(self, name):
        d = MagicMock()
        d.name = name
        return d

    def _adv(self, mfr=None):
        a = MagicMock()
        a.manufacturer_data = mfr or {}
        return a

    def test_nom_zwift(self):
        self.assertTrue(interface.est_click(self._device("Zwift Click"), self._adv()))

    def test_nom_click(self):
        self.assertTrue(interface.est_click(self._device("my click remote"), self._adv()))

    def test_nom_sf2(self):
        self.assertTrue(interface.est_click(self._device("SF2 device"), self._adv()))

    def test_manufacturer_id_zwift(self):
        self.assertTrue(interface.est_click(
            self._device("Unknown"),
            self._adv(mfr={interface.ZWIFT_MFR: b"\x00"})))

    def test_appareil_non_zwift(self):
        self.assertFalse(interface.est_click(
            self._device("HeadphonesXYZ"), self._adv()))

    def test_nom_none(self):
        self.assertFalse(interface.est_click(self._device(None), self._adv()))


# ── Tests : constantes ────────────────────────────────────────────────────────

class TestConstants(unittest.TestCase):

    def test_touche_plus_est_k(self):
        self.assertEqual(interface.TOUCHE_PLUS, "k")

    def test_touche_moins_est_i(self):
        self.assertEqual(interface.TOUCHE_MOINS, "i")

    def test_debounce_positif(self):
        self.assertGreater(interface.DEBOUNCE, 0)

    def test_notif_uuids_non_vide(self):
        self.assertGreater(len(interface.NOTIF_UUIDS), 0)

    def test_write_uuid_defini(self):
        self.assertTrue(interface.WRITE_UUID.startswith("00000003"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
