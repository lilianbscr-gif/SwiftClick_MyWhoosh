"""
conftest.py — Fixtures pytest partagées pour tous les tests.

Utilise ButtonShim plutôt que App pour éviter toute dépendance tkinter dans les tests.
ButtonShim reprend _on_data directement depuis App (même code, pas de duplication)
mais remplace _ui par un appel direct et n'a pas besoin de fenêtre tkinter.
"""
import threading
import time
import pytest
import pynput.keyboard as pyk

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import interface as m
from logger import EventLogger


class ButtonShim:
    """
    Double de test pour App._on_data — pas de tkinter.
    Emprunte _on_data directement depuis App (via binding de méthode non-liée)
    pour garantir qu'on teste exactement le même code que la production.
    """
    def __init__(self, logger: EventLogger):
        self._btn_pressed  = [False, False]
        self._last_fire    = [0.0,   0.0]
        self._global_key   = None
        self._device_addrs = ["AC:08", "1C:7E"]  # adresses fictives pour les tests
        self._lock           = threading.Lock()
        self._logger         = logger
        self.keyboard_presses: list = []
        self._count          = 0

    def _fire_action(self, label: str):
        self._count += 1

    def _ui(self, fn, *args, **kwargs):
        """Appel direct (pas de after() tkinter) — correct pour les tests."""
        fn(*args, **kwargs)


# Bind _on_data depuis App sans instancier tkinter.
# Quand appelé sur ButtonShim, self est le shim → tous les attributs sont présents.
ButtonShim._on_data = m.App._on_data


@pytest.fixture
def logger():
    return EventLogger(enabled=False)


@pytest.fixture
def app(logger):
    """ButtonShim avec keyboard mocké."""
    shim = ButtonShim(logger)
    pyk.Controller.press   = lambda self, k: shim.keyboard_presses.append(("press",   k))
    pyk.Controller.release = lambda self, k: shim.keyboard_presses.append(("release", k))
    return shim


def replay(app, sequence, idx: int = 0, concurrent: bool = False) -> int:
    """Rejoue une BLESequence et retourne le nombre de fires."""
    frames = sequence.frames
    delays = sequence.delays_ms
    fired_before = len([e for e in app.keyboard_presses if e[0] == "press"])

    if concurrent and len(frames) >= 2:
        barrier = threading.Barrier(2)

        def call(frame, _idx):
            barrier.wait()
            app._on_data(frame, _idx)

        t1 = threading.Thread(target=call, args=(frames[0], idx))
        t2 = threading.Thread(target=call, args=(frames[1], idx))
        t1.start(); t2.start()
        t1.join();  t2.join()
        rest_start = 2
    else:
        rest_start = 0

    for i in range(rest_start, len(frames)):
        delay = delays[i] if i < len(delays) else 0
        if delay > 0:
            time.sleep(delay / 1000)
        app._on_data(frames[i], idx)

    fired_after = len([e for e in app.keyboard_presses if e[0] == "press"])
    return fired_after - fired_before
