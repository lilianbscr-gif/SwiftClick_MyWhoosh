"""
interface.py  —  Zwift Click V2 → MyWhoosh
Double-cliquez sur Lancer.bat pour démarrer.
Prérequis : pip install bleak pynput
"""

import asyncio, threading, time, tkinter as tk
from tkinter import scrolledtext
from datetime import datetime
from bleak import BleakClient, BleakScanner
from pynput.keyboard import Key, Controller
from logger import EventLogger

# ── Configuration ────────────────────────────────────────────
TOUCHE_PLUS  = 'k'
TOUCHE_MOINS = 'i'

# Détection bouton par masque BLE (comme bikecontrol/OpenBikeControl) :
#   0xDF = bit 5 de data[3] = bit 12 du buttonMap = SHFT_UP_R = bouton PLUS
#   0xFD = bit 1 de data[3] = bit 8  du buttonMap = SHFT_UP_L = bouton MINUS
# Mapping par MASQUE, jamais par idx — cohérent avec le protocole Zwift Click V2.

DEBOUNCE = 0.05   # s — anti-rebond capteur par appareil (50ms)

KEEPALIVE_INTERVAL = 3.0    # s — le device dort après ~5s sans activité, keepalive à 3s
SILENCE_WARN       = 5.0    # s — alerte visuelle + burst de réveil (pas de déconnexion)
SILENCE_GRACE      = 20.0   # s — délai avant armement watchdog (connexion + handshake)
# ─────────────────────────────────────────────────────────────

WRITE_UUID   = "00000003-19ca-4651-86e5-fa29dcdd09d1"
BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"
RIDEON       = b"RideOn"
ZWIFT_MFR    = 0x094A
NOTIF_UUIDS  = [
    "00000002-19ca-4651-86e5-fa29dcdd09d1",
    "00000100-19ca-4651-86e5-fa29dcdd09d1",
    "00000101-19ca-4651-86e5-fa29dcdd09d1",
    "00000102-19ca-4651-86e5-fa29dcdd09d1",
]

keyboard = Controller()

# ── Palette futuriste — couleurs froides ──────────────────────
_C = {
    "bg0":   "#020810",   # fond profond (quasi-noir bleuté)
    "bg1":   "#05101e",   # fond fenêtre
    "bg2":   "#081828",   # panneau / section
    "bg3":   "#0c2038",   # surface élevée
    "cyan":  "#00d4ff",   # néon primaire
    "cyand": "#005f77",   # cyan atténué
    "cyang": "#001d25",   # cyan très dim (glow bg)
    "blue":  "#0077ee",   # accent secondaire
    "ice":   "#cce8ff",   # texte brillant
    "ice2":  "#5a8aaa",   # texte moyen
    "ice3":  "#1a3550",   # texte dim
    "green": "#00ffcc",   # succès
    "red":   "#ff1a44",   # erreur / stop
    "pink":  "#ff3366",   # bouton MOINS connecté
    "ora":   "#ff8c00",   # alerte
}


def est_click(device, adv):
    name = (device.name or "").lower()
    mfr  = adv.manufacturer_data or {}
    return "zwift" in name or "sf2" in name or "click" in name or ZWIFT_MFR in mfr


def detect_key(data: bytearray) -> str | None:
    """Décode les trames BLE du Zwift Click sur UUID 00000002 (après activation RideOn).

    Format A — data[0]=0x23, bitmask en data[3] (seul format actif après RideOn) :
      mask=0xFF           → idle toutes les ~90 ms, ignoré
      bit 5 (0x20) à 0   → bouton +   (mask ex. 0xDF)
      bit 1 (0x02) à 0   → bouton −   (mask ex. 0xFD)
      Confirmé diagnostic : bouton minus envoie 23 08 ff fd ff ff 0f

    Autres paquets sur 00000002 (19 10 50 etc.) : data[0]≠0x23 → ignorés.
    """
    if not data or data[0] != 0x23 or len(data) < 5:
        return None

    mask = data[3]
    if mask == 0xFF:
        return None
    if not (mask & 0x20):
        return TOUCHE_PLUS
    if not (mask & 0x02):
        return TOUCHE_MOINS
    return None


def rssi_quality(rssi: int) -> tuple[str, str, str]:
    """Retourne (barres, couleur_hex, label) depuis un RSSI en dBm."""
    if rssi >= -60: return "▰▰▰▰▰", _C["cyan"],  "OPTIMAL"
    if rssi >= -70: return "▰▰▰▰▱", _C["cyan"],  "BON"
    if rssi >= -80: return "▰▰▰▱▱", _C["ora"],   "MOYEN"
    if rssi >= -90: return "▰▰▱▱▱", _C["ora"],   "FAIBLE"
    return               "▰▱▱▱▱", _C["red"],    "CRITIQUE"


def battery_color(pct: int) -> str:
    if pct > 50: return _C["cyan"]
    if pct > 20: return _C["ora"]
    return _C["red"]


# ── Carte device — style octagonal futuriste ─────────────────
def make_click_canvas(parent, side="plus", connected=False):
    W, H = 125, 158
    c = tk.Canvas(parent, width=W, height=H,
                  bg=_C["bg0"], highlightthickness=0)

    CUT = 18  # découpe des coins pour l'octogone
    # Sommets de l'octogone
    pts = [CUT, 0,  W-CUT, 0,  W, CUT,  W, H-CUT,
           W-CUT, H,  CUT, H,  0, H-CUT,  0, CUT]

    if connected:
        body   = _C["bg3"]
        edge   = _C["cyan"]
        edged  = _C["cyand"]
        edgeg  = _C["cyang"]
        lbl_c  = _C["ice2"]
    else:
        body   = _C["bg2"]
        edge   = _C["ice3"]
        edged  = "#0d1f2e"
        edgeg  = _C["bg0"]
        lbl_c  = _C["ice3"]

    if side == "plus":
        btn_fill = _C["cyan"]  if connected else _C["ice3"]
        btn_edge = _C["cyan"]  if connected else _C["ice3"]
        sym_fill = _C["bg0"]   if connected else _C["bg2"]
        symbol   = "+"
        key_lbl  = "SHIFT +"
    else:
        btn_fill = _C["pink"]  if connected else "#1a0813"
        btn_edge = _C["pink"]  if connected else _C["ice3"]
        sym_fill = "white"     if connected else _C["ice3"]
        symbol   = "−"
        key_lbl  = "SHIFT −"

    # Corps (remplissage + double bordure)
    c.create_polygon(pts, fill=body,  outline="")
    c.create_polygon(pts, fill="",    outline=edged, width=1)
    c.create_polygon(pts, fill="",    outline=edge,  width=2)

    # Crochets de coin (effet HUD)
    blen = 12
    for (x1c, y1c, x2c, y2c, x3c, y3c) in [
        (0, CUT+blen, 0, CUT, blen, CUT),
        (W-blen, CUT, W, CUT, W, CUT+blen),
        (0, H-CUT-blen, 0, H-CUT, blen, H-CUT),
        (W-blen, H-CUT, W, H-CUT, W, H-CUT-blen),
    ]:
        c.create_line(x1c, y1c, x2c, y2c, x3c, y3c,
                      fill=edge, width=2)

    # Ligne séparatrice haute
    c.create_line(CUT, 26, W-CUT, 26, fill=edged, width=1)

    # Bouton principal
    bx, by = W // 2, 72
    R = 28
    # Anneau de glow (simulé avec plusieurs cercles de plus en plus dim)
    if connected:
        c.create_oval(bx-R-6, by-R-6, bx+R+6, by+R+6,
                      fill=edgeg, outline="")
        c.create_oval(bx-R-3, by-R-3, bx+R+3, by+R+3,
                      fill="", outline=edged, width=1)
    # Bouton
    c.create_oval(bx-R, by-R, bx+R, by+R,
                  fill=btn_fill, outline=btn_edge, width=2)
    c.create_text(bx, by, text=symbol,
                  font=("Segoe UI", 26, "bold"), fill=sym_fill)

    # Ligne séparatrice basse
    c.create_line(CUT, H-38, W-CUT, H-38, fill=edged, width=1)

    # LED + glow
    lx, ly = W // 2, H - 26
    if connected:
        c.create_oval(lx-8, ly-8, lx+8, ly+8, fill=edgeg, outline="")
    c.create_oval(lx-4, ly-4, lx+4, ly+4,
                  fill=edge if connected else edged, outline="")

    # Étiquette
    c.create_text(W // 2, H - 10, text=key_lbl,
                  font=("Consolas", 7, "bold"), fill=lbl_c)

    return c


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Zwift Click V2 → MyWhoosh")
        self.resizable(False, False)
        self.configure(bg=_C["bg1"])

        self._loop    = None
        self._thread  = None
        self._running = False
        self._btn_pressed    = [False, False]  # état bouton par appareil (machine à états)
        self._last_fire      = [0.0,   0.0]   # horodatage du dernier tir par appareil
        self._global_key     = None            # touche globalement active (bikecontrol: _lastButtonsClicked)
        self._device_addrs   = [None,  None]   # MAC par idx — pour les logs
        self._count   = 0
        self._lock    = threading.Lock()
        self._canvas  = [None, None]
        self._connected = [False, False]
        self._logger  = EventLogger()      # journal structuré → logs/events_*.jsonl

        # Indicateurs batterie et signal
        self._battery_lbl = [None, None]
        self._rssi_lbl    = [None, None]

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        BG  = _C["bg1"]
        BG2 = _C["bg2"]
        BG3 = _C["bg3"]
        CYN = _C["cyan"]
        I3  = _C["ice3"]
        PAD = 12

        # ── En-tête ──────────────────────────────────────────
        tk.Frame(self, bg=_C["cyand"], height=2).pack(fill="x")

        hdr = tk.Frame(self, bg=BG, pady=6)
        hdr.pack(fill="x")
        tk.Label(hdr, text="◈  ZWIFT CLICK  ──  MYWHOOSH  ◈",
                 font=("Consolas", 12, "bold"), fg=CYN, bg=BG
                 ).pack()
        tk.Label(hdr, text="SYSTÈME DE CONTRÔLE BLUETOOTH",
                 font=("Consolas", 7), fg=I3, bg=BG
                 ).pack()

        tk.Frame(self, bg=_C["cyand"], height=1).pack(fill="x")

        # ── Cartes devices ────────────────────────────────────
        clicks_frame = tk.Frame(self, bg=BG2, pady=2)
        clicks_frame.pack(fill="x", padx=PAD, pady=(PAD, 2))

        for col, (side, key) in enumerate(
                [("plus", TOUCHE_PLUS), ("moins", TOUCHE_MOINS)]):
            frame = tk.Frame(clicks_frame, bg=BG2)
            frame.grid(row=0, column=col, padx=14, pady=8)

            cvs = make_click_canvas(frame, side=side, connected=False)
            cvs.pack()
            self._canvas[col] = cvs

            tk.Label(frame, text=f"[ {key} ]",
                     font=("Consolas", 8, "bold"),
                     fg=_C["cyand"], bg=BG2
                     ).pack(pady=(3, 0))

            lbl = tk.Label(frame, text="OFFLINE",
                           font=("Consolas", 7), fg=I3, bg=BG2)
            lbl.pack()
            if col == 0: self._status_plus  = lbl
            else:        self._status_moins = lbl

            info = tk.Frame(frame, bg=BG2)
            info.pack(fill="x", pady=(2, 0))

            bat = tk.Label(info, text="BAT: —",
                           font=("Consolas", 7), fg=I3, bg=BG2, anchor="w")
            bat.pack(side="left", padx=2)

            sig = tk.Label(info, text="SIG: —",
                           font=("Consolas", 7), fg=I3, bg=BG2, anchor="e")
            sig.pack(side="right", padx=2)

            self._battery_lbl[col] = bat
            self._rssi_lbl[col]    = sig

        clicks_frame.columnconfigure(0, weight=1)
        clicks_frame.columnconfigure(1, weight=1)

        # ── Bouton principal ──────────────────────────────────
        tk.Frame(self, bg=_C["cyand"], height=1).pack(fill="x", padx=PAD)

        self._btn = tk.Button(
            self, text="▶  INITIALISER CONNEXION",
            font=("Consolas", 10, "bold"),
            fg=_C["bg0"], bg=CYN,
            activebackground=_C["cyand"], activeforeground=_C["bg0"],
            bd=0, padx=16, pady=10,
            cursor="hand2", command=self._toggle)
        self._btn.pack(pady=PAD, padx=PAD, fill="x")

        # ── Barre d'action ────────────────────────────────────
        bar = tk.Frame(self, bg=BG3, pady=7)
        bar.pack(fill="x", padx=PAD, pady=(0, PAD))

        self._last_lbl = tk.Label(bar, text="STANDBY",
                                   font=("Consolas", 9, "bold"),
                                   fg=I3, bg=BG3)
        self._last_lbl.pack(side="left", padx=10)

        self._count_var = tk.StringVar(value="0000×")
        tk.Label(bar, textvariable=self._count_var,
                 font=("Consolas", 9, "bold"), fg=I3, bg=BG3
                 ).pack(side="right", padx=10)

        # ── Journal ───────────────────────────────────────────
        tk.Label(self, text="── JOURNAL SYSTÈME ──",
                 font=("Consolas", 7, "bold"), fg=I3, bg=BG
                 ).pack(anchor="w", padx=PAD, pady=(0, 2))

        self._log_box = scrolledtext.ScrolledText(
            self, height=6, width=52,
            font=("Consolas", 7),
            bg=_C["bg0"], fg=I3,
            insertbackground=CYN,
            state="disabled", bd=0, relief="flat")
        self._log_box.pack(padx=PAD, pady=(0, PAD))

        self._log_box.tag_config("ok",  foreground=_C["cyan"])
        self._log_box.tag_config("err", foreground=_C["red"])
        self._log_box.tag_config("act", foreground=_C["ora"])
        self._log_box.tag_config("dim", foreground=_C["ice3"])

        tk.Frame(self, bg=_C["cyand"], height=1).pack(fill="x")

        self._log("SYS INIT  ·  READY", "ok")

    # ── Contrôles ─────────────────────────────────────────────
    def _toggle(self):
        if self._running: self._stop()
        else:             self._start()

    def _start(self):
        self._running = True
        self._btn.configure(text="■  DÉCONNECTER",
                             bg=_C["red"], activebackground="#aa0022")
        self._log("SCAN BLUETOOTH…", "dim")
        self._loop   = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _stop(self):
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._btn.configure(text="▶  INITIALISER CONNEXION",
                             bg=_C["cyan"], activebackground=_C["cyand"])
        for i in range(2):
            self._refresh_canvas(i, False, "OFFLINE")
            self._clear_device_info(i)
        self._log("SYSTÈME ARRÊTÉ", "dim")

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        except Exception:
            pass

    # ── BLE ───────────────────────────────────────────────────
    async def _main(self):
        tasks     = [None, None]
        addresses = [None, None]

        try:
            while self._running:
                for i in range(2):
                    if tasks[i] is not None and tasks[i].done():
                        try:   await tasks[i]
                        except Exception: pass
                        tasks[i]     = None
                        addresses[i] = None

                missing = [i for i in range(2) if tasks[i] is None]
                if not missing:
                    await asyncio.sleep(0.5)
                    continue

                try:
                    results = await BleakScanner.discover(timeout=8.0, return_adv=True)
                    # Garde (device, adv_data) pour avoir le RSSI initial
                    clicks = [
                        (d, adv)
                        for _, (d, adv) in results.items()
                        if est_click(d, adv)
                    ]
                except Exception as e:
                    self._ui(self._log, f"Erreur scan : {e}", "err")
                    await asyncio.sleep(3)
                    continue

                used      = {a for a in addresses if a}
                available = [(d, adv) for d, adv in clicks if d.address not in used]

                if not available:
                    self._ui(self._log, "Aucun Click disponible, nouvelle tentative…", "dim")
                    await asyncio.sleep(3)
                    continue

                self._ui(self._log, f"{len(available)} Click(s) disponible(s).", "ok")
                for i, (dev, adv) in zip(missing, available):
                    if not self._running:
                        break
                    addresses[i] = dev.address
                    tasks[i]     = asyncio.create_task(self._connect(dev, adv, i))
                    await asyncio.sleep(1)

                await asyncio.sleep(0.5)
        finally:
            for t in tasks:
                if t and not t.done():
                    t.cancel()
            await asyncio.gather(*[t for t in tasks if t], return_exceptions=True)

    async def _connect(self, device, adv_data, idx):
        addr       = device.address
        notif_time = [time.monotonic()]

        # RSSI capturé au moment du scan
        initial_rssi = getattr(adv_data, "rssi", None)
        if initial_rssi is not None:
            self._ui(self._update_rssi, idx, initial_rssi)

        ready = [False]   # bloque les données bouton pendant la phase de connexion

        def notif_cb(sender, d, _idx=idx):
            notif_time[0] = time.monotonic()
            d_arr = bytearray(d)
            uuid_short = str(getattr(sender, "uuid", "?"))[:8]
            self._logger.ble_raw(_idx, uuid_short, d_arr, ready[0])
            if ready[0]:
                self._on_data(d_arr, _idx)

        self._device_addrs[idx] = addr
        self._logger.connect(idx, addr)
        self._ui(self._refresh_canvas, idx, False, "Connexion…")
        try:
            async with BleakClient(addr) as client:
                await asyncio.sleep(0.5)

                short = addr[-8:]  # partie unique pour les logs : "03:AC:08" / "3F:1C:7E"

                # UUID 00000004 : le device acquitte chaque keepalive sur 00000003
                # avec "RideOn" sur 00000004. On souscrit pour mettre à jour notif_time.
                def keepalive_ack_cb(*_):
                    notif_time[0] = time.monotonic()

                try:
                    await client.start_notify(
                        "00000004-19ca-4651-86e5-fa29dcdd09d1", keepalive_ack_cb
                    )
                except Exception:
                    pass

                # Activation RideOn
                try:
                    await client.write_gatt_char(WRITE_UUID, RIDEON, response=False)
                except Exception:
                    pass

                souscrit = []
                for uuid in NOTIF_UUIDS:
                    try:
                        await client.start_notify(uuid, notif_cb)
                        souscrit.append(uuid)
                    except Exception:
                        pass

                if not souscrit:
                    self._ui(self._refresh_canvas, idx, False, "Erreur notifications")
                    self._ui(self._log, f"Aucune notif sur {addr} — reconnexion", "err")
                    return

                label = "SHIFT +" if idx == 0 else "SHIFT −"
                self._ui(self._refresh_canvas, idx, True, addr)
                self._ui(self._log, f"{label} connecté ({addr})", "ok")

                battery = await self._read_battery(client)
                if battery is not None:
                    self._ui(self._update_battery, idx, battery)
                    self._ui(self._log, f"{label} batterie : {battery}%", "dim")
                else:
                    self._ui(self._update_battery, idx, None)

                self._btn_pressed[idx] = False
                self._last_fire[idx]   = 0.0
                notif_time[0]   = time.monotonic()
                subscribe_time  = time.monotonic()
                next_rssi_check = subscribe_time + 5.0
                ready[0] = True
                self._logger.ready(idx, addr)

                next_keepalive = time.monotonic() + 2.0  # premier keepalive rapide

                while self._running and client.is_connected:
                    await asyncio.sleep(0.5)
                    now     = time.monotonic()
                    silence = now - notif_time[0]
                    elapsed = now - subscribe_time

                    # ── Watchdog silence ──────────────────────────────────
                    # Pas de déconnexion forcée — elle cause plus de bugs qu'elle n'en résout.
                    # Sur silence > SILENCE_WARN : status orange + burst de réveil RideOn.
                    # La déconnexion BLE reste gérée par while client.is_connected.
                    if elapsed > SILENCE_GRACE:
                        if silence > SILENCE_WARN:
                            self._logger.led_warn(idx, addr, silence)
                            self._ui(self._update_status, idx,
                                     f"LED éteinte ({silence:.0f}s) — tentative réveil",
                                     "#f5a623")
                        else:
                            self._ui(self._update_status, idx,
                                     f"Connecté  •  {short}", "#4ecca3")

                    # Rafraîchissement RSSI toutes les 5 s
                    if now >= next_rssi_check:
                        try:
                            live_rssi = client.rssi
                            if live_rssi is not None:
                                self._ui(self._update_rssi, idx, live_rssi)
                        except Exception:
                            pass
                        next_rssi_check = now + 5.0

                    # Keepalive toutes les KEEPALIVE_INTERVAL secondes.
                    # Le device acquitte chaque write avec "RideOn" sur UUID 00000004.
                    if now >= next_keepalive:
                        try:
                            await client.write_gatt_char(WRITE_UUID, RIDEON, response=False)
                        except Exception:
                            pass
                        next_keepalive = now + KEEPALIVE_INTERVAL

                for uuid in souscrit:
                    try:   await client.stop_notify(uuid)
                    except Exception: pass

                self._logger.disconnect(idx, addr, "led_sleep_or_stop")
                self._ui(self._refresh_canvas, idx, False, "Déconnecté")
                self._ui(self._clear_device_info, idx)
                self._ui(self._log, f"Déconnecté : {addr}", "dim")

        except Exception as e:
            self._logger.disconnect(idx, addr, f"exception:{type(e).__name__}")
            self._ui(self._refresh_canvas, idx, False, "Erreur")
            self._ui(self._clear_device_info, idx)
            self._ui(self._log, f"Erreur {addr}: {e}", "err")

    async def _read_battery(self, client: BleakClient) -> int | None:
        """Lit le niveau de batterie via le Battery Service BLE standard (0x2A19)."""
        try:
            data = await client.read_gatt_char(BATTERY_UUID)
            return int(data[0])
        except Exception:
            return None

    def _on_data(self, data: bytearray, idx: int):
        # Format A uniquement (UUID 00000002 après RideOn)
        if not data or data[0] != 0x23 or len(data) < 5:
            return

        mask = data[3]
        addr = self._device_addrs[idx] or "?"

        if mask == 0xFF:
            self._btn_pressed[idx] = False
            # Approche bikecontrol : _global_key se remet à None seulement
            # quand TOUS les devices ont relâché (not any).
            if not any(self._btn_pressed):
                self._global_key = None
            self._logger.btn_release(idx, addr)
            return

        # Mapping par masque BLE — protocole bikecontrol/OpenBikeControl :
        # bit 5 de data[3] = 0 → bit 12 buttonMap = SHFT_UP_R = bouton PLUS
        # bit 1 de data[3] = 0 → bit 8  buttonMap = SHFT_UP_L = bouton MINUS
        if not (mask & 0x20):
            key = TOUCHE_PLUS
        elif not (mask & 0x02):
            key = TOUCHE_MOINS
        else:
            return  # masque inconnu

        label = "▲  Vitesse +" if key == TOUCHE_PLUS else "▼  Vitesse −"

        with self._lock:
            # Couche 1 — state machine par device (front montant uniquement)
            if self._btn_pressed[idx]:
                self._logger.btn_block(idx, "state_machine", mask, addr)
                return

            now = time.monotonic()

            # Couche 2 — debounce par device
            if (now - self._last_fire[idx]) < DEBOUNCE:
                self._logger.btn_block(idx, "debounce", mask, addr)
                return

            # Couche 3 — déduplication globale (bikecontrol: _lastButtonsClicked).
            # Si la MÊME touche est déjà active (tirée par un autre device),
            # on marque quand même ce device comme pressé (btn_pressed[idx]=True)
            # pour que la state machine bloque toutes ses notifications suivantes
            # jusqu'au vrai release (0xFF). Sans ce Set, après 100ms le device
            # repasserait btn_pressed=False et tirerait à nouveau — c'était le bug.
            if key == self._global_key:
                self._btn_pressed[idx] = True   # ← crucial : bloque les notifs suivantes
                self._logger.btn_block(idx, "global_dedup", mask, addr)
                return

            # Fire — nouvelle touche ou reprise après release global
            self._btn_pressed[idx]   = True
            self._last_fire[idx]     = now
            self._global_key         = key
            self._logger.btn_fire(idx, key, label, mask, addr)
            keyboard.type(key)

        self._ui(self._fire_action, label)

    def _fire_action(self, label):
        self._count += 1
        self._count_var.set(f"{self._count:04d}×")
        self._last_lbl.configure(text=label, fg=_C["cyan"])

    # ── UI helpers ────────────────────────────────────────────
    def _refresh_canvas(self, idx, connected, status_text):
        side = "plus" if idx == 0 else "moins"
        cvs  = self._canvas[idx]
        parent = cvs.master

        cvs.destroy()
        new_cvs = make_click_canvas(parent, side=side, connected=connected)
        new_cvs.pack()
        self._canvas[idx] = new_cvs

        lbl   = self._status_plus if idx == 0 else self._status_moins
        color = _C["cyan"] if connected else _C["ice3"]
        lbl.configure(text=status_text, fg=color)

    def _update_battery(self, idx: int, pct: int | None):
        """Met à jour l'étiquette de batterie pour le Click idx."""
        lbl = self._battery_lbl[idx]
        if pct is None:
            lbl.configure(text="BAT: —", fg=_C["ice3"])
        else:
            color  = battery_color(pct)
            filled = round(pct / 20)
            bar    = "▰" * filled + "▱" * (5 - filled)
            lbl.configure(text=f"▸{bar} {pct:3d}%", fg=color)

    def _update_status(self, idx: int, text: str, color: str):
        """Met à jour uniquement le label de statut (sans redessiner le canvas)."""
        lbl = self._status_plus if idx == 0 else self._status_moins
        lbl.configure(text=text, fg=color)

    def _update_rssi(self, idx: int, rssi: int):
        """Met à jour l'étiquette de signal pour le Click idx."""
        lbl = self._rssi_lbl[idx]
        bars, color, _ = rssi_quality(rssi)
        lbl.configure(text=f"◈{bars}", fg=color)

    def _clear_device_info(self, idx: int):
        """Remet batterie, signal et état bouton à zéro (déconnexion ou arrêt)."""
        self._btn_pressed[idx]   = False
        self._last_fire[idx]     = 0.0
        if not any(self._btn_pressed):
            self._global_key = None
        self._battery_lbl[idx].configure(text="BAT: —",  fg=_C["ice3"])
        self._rssi_lbl[idx].configure(   text="SIG: —",  fg=_C["ice3"])

    def _log(self, msg, tag="dim"):
        now = datetime.now().strftime("%H:%M:%S")
        self._log_box.configure(state="normal")
        self._log_box.insert("end", f"[{now}] {msg}\n", tag)
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _ui(self, fn, *args, **kwargs):
        self.after(0, fn, *args, **kwargs)

    def _on_close(self):
        self._stop()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
