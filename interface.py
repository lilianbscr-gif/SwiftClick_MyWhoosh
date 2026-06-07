"""
interface.py  —  Zwift Click V2 → MyWhoosh  (PySide6 + qasync)
Double-cliquez sur Lancer.bat pour démarrer.
Prérequis : pip install bleak pynput PySide6 qasync
"""

import asyncio, time, subprocess, json, os, sys, threading
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QPlainTextEdit,
)
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPainterPath,
    QLinearGradient, QRadialGradient, QTextCharFormat, QTextCursor,
    QIcon,
)

import qasync

from bleak import BleakClient, BleakScanner
from pynput.keyboard import Controller
from logger import EventLogger
from intervals_client import IntervalsClient

# ── Configuration ────────────────────────────────────────────
TOUCHE_PLUS  = 'k'
TOUCHE_MOINS = 'i'

DEBOUNCE = 0.05

KEEPALIVE_INTERVAL = 3.0
SILENCE_WARN       = 5.0
SILENCE_GRACE      = 20.0
LOCK_TIMEOUT       = 55.0

WRITE_UUID   = "00000003-19ca-4651-86e5-fa29dcdd09d1"
BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"
RIDEON       = b"RideOn"
UNLOCK_CMD   = bytes([0xFF, 0x04, 0x00])
ZWIFT_MFR    = 0x094A

UNLOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "unlock_state.json")
NOTIF_UUIDS = [
    "00000002-19ca-4651-86e5-fa29dcdd09d1",
    "00000100-19ca-4651-86e5-fa29dcdd09d1",
    "00000101-19ca-4651-86e5-fa29dcdd09d1",
    "00000102-19ca-4651-86e5-fa29dcdd09d1",
]

keyboard = Controller()

# ── Palette futuriste ────────────────────────────────────────
_C = {
    "bg0":   "#020810",
    "bg1":   "#05101e",
    "bg2":   "#081828",
    "bg3":   "#0c2038",
    "cyan":  "#00d4ff",
    "cyand": "#005f77",
    "cyang": "#001d25",
    "blue":  "#0077ee",
    "ice":   "#e0f4ff",
    "ice2":  "#9ec8e8",
    "ice3":  "#6a9abf",
    "green": "#00ffcc",
    "red":   "#ff1a44",
    "pink":  "#ff3366",
    "ora":   "#ff8c00",
}


# ── Helpers persistance unlock 24h ───────────────────────────

def _load_unlock_state() -> dict:
    try:
        with open(UNLOCK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_unlock_timestamp(device_addr: str):
    state = _load_unlock_state()
    state[device_addr.upper()] = datetime.now().isoformat()
    try:
        with open(UNLOCK_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def is_device_unlocked_24h(device_addr: str) -> bool:
    state = _load_unlock_state()
    ts_str = state.get(device_addr.upper())
    if not ts_str:
        return False
    try:
        last_unlock = datetime.fromisoformat(ts_str)
        return datetime.now() - last_unlock < timedelta(hours=24)
    except Exception:
        return False


def est_click(device, adv):
    name = (device.name or "").lower()
    mfr  = adv.manufacturer_data or {}
    return "zwift" in name or "sf2" in name or "click" in name or ZWIFT_MFR in mfr


def detect_key(data: bytearray) -> str | None:
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
    if rssi >= -60: return "▰▰▰▰▰", _C["cyan"],  "OPTIMAL"
    if rssi >= -70: return "▰▰▰▰▱", _C["cyan"],  "BON"
    if rssi >= -80: return "▰▰▰▱▱", _C["ora"],   "MOYEN"
    if rssi >= -90: return "▰▰▱▱▱", _C["ora"],   "FAIBLE"
    return               "▰▱▱▱▱", _C["red"],    "CRITIQUE"


def battery_color(pct: int) -> str:
    if pct > 50: return _C["cyan"]
    if pct > 20: return _C["ora"]
    return _C["red"]


# ── ClickCard — widget QPainter style HUD ────────────────────

class ClickCard(QWidget):
    """Carte device Zwift Click V2 — octogone futuriste dessiné avec QPainter."""

    W, H, CUT = 132, 168, 20

    def __init__(self, side: str = "plus", parent=None):
        super().__init__(parent)
        self.side      = side
        self.connected = False
        self.setFixedSize(self.W, self.H)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def set_connected(self, connected: bool):
        if self.connected != connected:
            self.connected = connected
            self.update()

    def _octagon_path(self) -> QPainterPath:
        W, H, C = self.W, self.H, self.CUT
        p = QPainterPath()
        p.moveTo(C, 0)
        p.lineTo(W - C, 0)
        p.lineTo(W, C)
        p.lineTo(W, H - C)
        p.lineTo(W - C, H)
        p.lineTo(C, H)
        p.lineTo(0, H - C)
        p.lineTo(0, C)
        p.closeSubpath()
        return p

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        W, H, C = self.W, self.H, self.CUT
        conn = self.connected

        accent     = QColor(_C["cyan"]) if self.side == "plus" else QColor(_C["pink"])
        accent_dim = QColor(_C["cyand"]) if self.side == "plus" else QColor("#3d0018")

        path = self._octagon_path()

        # ── Corps avec dégradé ────────────────────────────────
        grad = QLinearGradient(QPointF(0, 0), QPointF(0, H))
        if conn:
            grad.setColorAt(0, QColor("#0f2840"))
            grad.setColorAt(1, QColor("#07182a"))
        else:
            grad.setColorAt(0, QColor("#081828"))
            grad.setColorAt(1, QColor("#04101c"))
        p.setPen(Qt.NoPen)
        p.fillPath(path, QBrush(grad))

        # Glow de fond quand connecté
        if conn:
            glow = QColor(accent)
            glow.setAlpha(12)
            p.fillPath(path, QBrush(glow))

        # ── Bordure double ────────────────────────────────────
        p.setPen(QPen(accent_dim, 1))
        p.drawPath(path)
        border_color = QColor(accent) if conn else QColor("#2a4060")
        p.setPen(QPen(border_color, 2))
        p.drawPath(path)

        # ── Crochets HUD ──────────────────────────────────────
        blen = 14
        bracket_color = QColor(accent) if conn else QColor("#1e3550")
        p.setPen(QPen(bracket_color, 2, Qt.SolidLine, Qt.SquareCap))
        corners = [
            [(0, C + blen), (0, C), (blen, C)],
            [(W - blen, C), (W, C), (W, C + blen)],
            [(0, H - C - blen), (0, H - C), (blen, H - C)],
            [(W - blen, H - C), (W, H - C), (W, H - C - blen)],
        ]
        for pts in corners:
            for i in range(len(pts) - 1):
                p.drawLine(QPointF(*pts[i]), QPointF(*pts[i + 1]))

        # ── Séparateurs ───────────────────────────────────────
        p.setPen(QPen(accent_dim, 1))
        p.drawLine(QPointF(C, 30), QPointF(W - C, 30))
        p.drawLine(QPointF(C, H - 42), QPointF(W - C, H - 42))

        # ── Bouton principal ──────────────────────────────────
        cx, cy, R = W / 2.0, 82.0, 32.0

        if conn:
            for r_off, alpha in [(14, 10), (9, 22), (5, 38)]:
                ring = QColor(accent)
                ring.setAlpha(alpha)
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(ring))
                p.drawEllipse(QPointF(cx, cy), R + r_off, R + r_off)

        if self.side == "plus":
            btn_fill = QColor(_C["cyan"]) if conn else QColor("#0d2030")
        else:
            btn_fill = QColor(_C["pink"]) if conn else QColor("#180810")

        btn_grad = QRadialGradient(QPointF(cx - R * 0.25, cy - R * 0.3), R * 1.6)
        if conn:
            lighter = QColor(btn_fill).lighter(140)
            btn_grad.setColorAt(0, lighter)
            btn_grad.setColorAt(1, btn_fill)
        else:
            btn_grad.setColorAt(0, btn_fill)
            btn_grad.setColorAt(1, QColor(btn_fill).darker(130))

        p.setPen(QPen(QColor(accent) if conn else QColor("#1e3550"), 2))
        p.setBrush(QBrush(btn_grad))
        p.drawEllipse(QPointF(cx, cy), R, R)

        # Symbole +/−
        sym = "+" if self.side == "plus" else "−"
        sym_color = QColor(_C["bg0"]) if conn else QColor("#2a4060")
        p.setPen(sym_color)
        font = QFont("Segoe UI", 24, QFont.Bold)
        p.setFont(font)
        p.drawText(QRectF(cx - R, cy - R, R * 2, R * 2), Qt.AlignCenter, sym)

        # ── LED indicateur ────────────────────────────────────
        lx, ly = W / 2.0, float(H - 24)

        if conn:
            led_glow = QRadialGradient(QPointF(lx, ly), 12)
            g_col = QColor(accent)
            g_col.setAlpha(140)
            led_glow.setColorAt(0, QColor(accent))
            led_glow.setColorAt(0.4, g_col)
            led_glow.setColorAt(1, Qt.transparent)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(led_glow))
            p.drawEllipse(QPointF(lx, ly), 12, 12)

        led_col = QColor(accent) if conn else QColor("#1a3040")
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(led_col))
        p.drawEllipse(QPointF(lx, ly), 4.5, 4.5)

        # ── Étiquette touche ──────────────────────────────────
        lbl_col = QColor(_C["ice2"]) if conn else QColor(_C["ice3"])
        p.setPen(lbl_col)
        font_sm = QFont("Consolas", 6, QFont.Bold)
        p.setFont(font_sm)
        p.drawText(QRectF(0, H - 16, W, 16), Qt.AlignCenter,
                   "SHIFT +" if self.side == "plus" else "SHIFT −")

        p.end()


# ── Barre de séparation ──────────────────────────────────────

def _sep(parent: QWidget, color: str = _C["cyand"], height: int = 1) -> QFrame:
    line = QFrame(parent)
    line.setFixedHeight(height)
    line.setStyleSheet(f"background-color: {color}; border: none;")
    return line


def _label(text: str, color: str, size: int = 7, bold: bool = False,
           parent: QWidget = None) -> QLabel:
    lbl = QLabel(text, parent)
    w = "bold" if bold else "normal"
    lbl.setStyleSheet(
        f"color: {color}; font-family: Consolas; font-size: {size}pt; font-weight: {w};"
        f" background: transparent;"
    )
    return lbl


# ── Application principale ───────────────────────────────────

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Zwift Click V2 → MyWhoosh")
        self.setFixedWidth(400)
        self.setWindowIcon(QIcon(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
        ))

        # ── État interne ──────────────────────────────────────
        self._running      = False
        self._ble_task     = None
        self._btn_pressed  = [False, False]
        self._last_fire    = [0.0, 0.0]
        self._global_key   = None
        self._device_addrs = [None, None]
        self._count        = 0
        self._lock         = threading.Lock()
        self._connected    = [False, False]
        self._logger       = EventLogger()
        self._intervals    = IntervalsClient()

        self._cards:       list[ClickCard | None] = [None, None]
        self._status_lbl:  list[QLabel | None]    = [None, None]
        self._battery_lbl: list[QLabel | None]    = [None, None]
        self._rssi_lbl:    list[QLabel | None]    = [None, None]
        self._perf_lbl:    dict[str, QLabel]      = {}

        self._build_ui()

        # Lancement auto MyWhoosh
        QTimer.singleShot(500, self._launch_mywhoosh)

        # Premier fetch intervals.icu
        if self._intervals.enabled:
            QTimer.singleShot(2000, self._fetch_intervals)

    # ── Construction UI ───────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        root.setStyleSheet(f"background-color: {_C['bg1']};")

        # En-tête
        vbox.addWidget(_sep(root, _C["cyand"], 2))
        hdr = QWidget()
        hdr.setStyleSheet(f"background-color: {_C['bg1']};")
        hdr_v = QVBoxLayout(hdr)
        hdr_v.setContentsMargins(0, 8, 0, 8)
        hdr_v.setSpacing(2)
        hdr_v.addWidget(_label("◈  ZWIFT CLICK  ──  MYWHOOSH  ◈",
                                _C["cyan"], 11, bold=True), 0, Qt.AlignHCenter)
        hdr_v.addWidget(_label("SYSTÈME DE CONTRÔLE BLUETOOTH",
                                _C["ice3"], 7), 0, Qt.AlignHCenter)
        vbox.addWidget(hdr)
        vbox.addWidget(_sep(root, _C["cyand"], 1))

        # Cartes devices
        cards_frame = QWidget()
        cards_frame.setStyleSheet(f"background-color: {_C['bg2']};")
        cards_h = QHBoxLayout(cards_frame)
        cards_h.setContentsMargins(14, 10, 14, 10)
        cards_h.setSpacing(16)

        for col, (side, key) in enumerate([("plus", TOUCHE_PLUS), ("moins", TOUCHE_MOINS)]):
            col_w = QWidget()
            col_w.setStyleSheet(f"background-color: {_C['bg2']};")
            col_v = QVBoxLayout(col_w)
            col_v.setContentsMargins(0, 0, 0, 0)
            col_v.setSpacing(3)
            col_v.setAlignment(Qt.AlignHCenter)

            card = ClickCard(side)
            self._cards[col] = card
            col_v.addWidget(card, 0, Qt.AlignHCenter)

            key_lbl = _label(f"[ {key} ]", _C["cyand"], 7, bold=True)
            col_v.addWidget(key_lbl, 0, Qt.AlignHCenter)

            status = _label("OFFLINE", _C["ice3"], 7)
            self._status_lbl[col] = status
            col_v.addWidget(status, 0, Qt.AlignHCenter)

            info_row = QWidget()
            info_row.setStyleSheet(f"background-color: {_C['bg2']};")
            info_h = QHBoxLayout(info_row)
            info_h.setContentsMargins(0, 0, 0, 0)
            info_h.setSpacing(4)

            bat = _label("BAT: —", _C["ice3"], 7)
            sig = _label("SIG: —", _C["ice3"], 7)
            self._battery_lbl[col] = bat
            self._rssi_lbl[col]    = sig
            info_h.addWidget(bat)
            info_h.addStretch()
            info_h.addWidget(sig)

            col_v.addWidget(info_row)
            cards_h.addWidget(col_w)

        vbox.addWidget(cards_frame)

        # Bouton connexion
        vbox.addWidget(_sep(root, _C["cyand"], 1))
        self._btn = QPushButton("▶  INITIALISER CONNEXION")
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.setFixedHeight(44)
        self._btn.setStyleSheet(self._btn_style(active=False))
        self._btn.clicked.connect(self._toggle)
        btn_wrap = QWidget()
        btn_wrap.setStyleSheet(f"background-color: {_C['bg1']};")
        bw = QHBoxLayout(btn_wrap)
        bw.setContentsMargins(12, 10, 12, 10)
        bw.addWidget(self._btn)
        vbox.addWidget(btn_wrap)

        # Barre d'action
        vbox.addWidget(_sep(root, _C["cyand"], 1))
        bar = QWidget()
        bar.setStyleSheet(f"background-color: {_C['bg3']};")
        bar_h = QHBoxLayout(bar)
        bar_h.setContentsMargins(12, 7, 12, 7)

        self._last_lbl = _label("STANDBY", _C["ice3"], 9, bold=True)
        self._count_lbl = _label("0000×", _C["ice3"], 9, bold=True)
        bar_h.addWidget(self._last_lbl)
        bar_h.addStretch()
        bar_h.addWidget(self._count_lbl)
        vbox.addWidget(bar)

        # Panneau intervals.icu
        vbox.addWidget(_sep(root, _C["cyand"], 1))
        perf_hdr = QWidget()
        perf_hdr.setStyleSheet(f"background-color: {_C['bg1']};")
        ph = QHBoxLayout(perf_hdr)
        ph.setContentsMargins(12, 4, 12, 2)
        ph.addWidget(_label("── PERFORMANCE DU JOUR ──", _C["ice3"], 7, bold=True))
        vbox.addWidget(perf_hdr)

        perf_frame = QWidget()
        perf_frame.setStyleSheet(f"background-color: {_C['bg3']};")
        pf_v = QVBoxLayout(perf_frame)
        pf_v.setContentsMargins(12, 6, 12, 6)
        pf_v.setSpacing(3)

        for lbl_text, key, unit in [
            ("FORME",   "ctl", "(CTL)"),
            ("FATIGUE", "atl", "(ATL)"),
            ("BALANCE", "tsb", "(TSB)"),
            ("FTP",     "ftp", "W    "),
        ]:
            row = QWidget()
            row.setStyleSheet(f"background-color: {_C['bg3']};")
            row_h = QHBoxLayout(row)
            row_h.setContentsMargins(0, 0, 0, 0)
            row_h.setSpacing(6)
            row_h.addWidget(_label(f"{lbl_text} {unit}", _C["ice3"], 7, parent=row),
                            0, Qt.AlignLeft)
            val_lbl = _label("—", _C["ice3"], 8, bold=True, parent=row)
            self._perf_lbl[key] = val_lbl
            row_h.addWidget(val_lbl, 1, Qt.AlignLeft)
            pf_v.addWidget(row)

        foot = QWidget()
        foot.setStyleSheet(f"background-color: {_C['bg3']};")
        foot_h = QHBoxLayout(foot)
        foot_h.setContentsMargins(0, 2, 0, 2)
        upd = _label("", _C["ice3"], 6, parent=foot)
        self._perf_lbl["updated"] = upd
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(22, 22)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {_C['cyand']};"
            f" font-family: Consolas; font-size: 9pt; border: none; }}"
            f"QPushButton:hover {{ color: {_C['cyan']}; }}"
        )
        refresh_btn.clicked.connect(self._fetch_intervals)
        foot_h.addWidget(upd)
        foot_h.addStretch()
        foot_h.addWidget(refresh_btn)
        pf_v.addWidget(foot)
        vbox.addWidget(perf_frame)

        # Journal
        vbox.addWidget(_sep(root, _C["cyand"], 1))
        log_hdr = QWidget()
        log_hdr.setStyleSheet(f"background-color: {_C['bg1']};")
        lh = QHBoxLayout(log_hdr)
        lh.setContentsMargins(12, 4, 12, 2)
        lh.addWidget(_label("── JOURNAL SYSTÈME ──", _C["ice3"], 7, bold=True))
        vbox.addWidget(log_hdr)

        self._log_box = QPlainTextEdit()
        self._log_box.setReadOnly(True)
        self._log_box.setFixedHeight(130)
        self._log_box.setStyleSheet(
            f"QPlainTextEdit {{"
            f"  background-color: {_C['bg0']};"
            f"  color: {_C['ice3']};"
            f"  font-family: Consolas; font-size: 7pt;"
            f"  border: none;"
            f"  padding: 4px;"
            f"}}"
        )
        self._log_box.setMaximumBlockCount(300)
        vbox.addWidget(self._log_box)
        vbox.addWidget(_sep(root, _C["cyand"], 1))

        self._log("SYS INIT  ·  READY", "ok")

    # ── Helpers style ─────────────────────────────────────────

    def _btn_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background-color: {_C['red']}; color: {_C['ice']};"
                f" font-family: Consolas; font-size: 10pt; font-weight: bold;"
                f" border: none; border-radius: 4px; }}"
                f"QPushButton:hover {{ background-color: #cc1133; }}"
            )
        return (
            f"QPushButton {{ background-color: {_C['cyan']}; color: {_C['bg0']};"
            f" font-family: Consolas; font-size: 10pt; font-weight: bold;"
            f" border: none; border-radius: 4px; }}"
            f"QPushButton:hover {{ background-color: #00b8e6; }}"
        )

    # ── Contrôles ─────────────────────────────────────────────

    def _toggle(self):
        if self._running:
            self._stop()
        else:
            self._start()

    def _start(self):
        self._running = True
        self._btn.setText("■  DÉCONNECTER")
        self._btn.setStyleSheet(self._btn_style(active=True))
        self._log("SCAN BLUETOOTH…", "dim")
        self._ble_task = asyncio.ensure_future(self._main())

    def _stop(self):
        self._running = False
        if self._ble_task and not self._ble_task.done():
            self._ble_task.cancel()
        self._ble_task = None
        self._btn.setText("▶  INITIALISER CONNEXION")
        self._btn.setStyleSheet(self._btn_style(active=False))
        for i in range(2):
            self._refresh_card(i, False, "OFFLINE")
            self._clear_device_info(i)
        self._log("SYSTÈME ARRÊTÉ", "dim")

    def closeEvent(self, event):
        self._stop()
        event.accept()

    # ── BLE ───────────────────────────────────────────────────

    async def _main(self):
        tasks     = [None, None]
        addresses = [None, None]

        try:
            while self._running:
                for i in range(2):
                    if tasks[i] is not None and tasks[i].done():
                        try:
                            await tasks[i]
                        except Exception:
                            pass
                        tasks[i]     = None
                        addresses[i] = None

                missing = [i for i in range(2) if tasks[i] is None]
                if not missing:
                    await asyncio.sleep(0.5)
                    continue

                try:
                    results = await BleakScanner.discover(timeout=8.0, return_adv=True)
                    clicks = [
                        (d, adv)
                        for _, (d, adv) in results.items()
                        if est_click(d, adv)
                    ]
                except Exception as e:
                    self._log(f"Erreur scan : {e}", "err")
                    await asyncio.sleep(3)
                    continue

                used      = {a for a in addresses if a}
                available = [(d, adv) for d, adv in clicks if d.address not in used]

                if not available:
                    self._log("Aucun Click disponible, nouvelle tentative…", "dim")
                    await asyncio.sleep(3)
                    continue

                self._log(f"{len(available)} Click(s) disponible(s).", "ok")
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
        addr  = device.address
        short = addr[-8:]

        initial_rssi = getattr(adv_data, "rssi", None)
        if initial_rssi is not None:
            self._update_rssi(idx, initial_rssi)

        notif_time    = [time.monotonic()]
        format_a_time = [time.monotonic()]

        self._device_addrs[idx] = addr
        label = "SHIFT +" if idx == 0 else "SHIFT −"

        while self._running:
            lock_detected = False
            ready = [False]

            def notif_cb(sender, d, _idx=idx):
                notif_time[0] = time.monotonic()
                d_arr = bytearray(d)
                if d_arr and d_arr[0] == 0x23:
                    format_a_time[0] = time.monotonic()
                uuid_short = str(getattr(sender, "uuid", "?"))[:8]
                self._logger.ble_raw(_idx, uuid_short, d_arr, ready[0])
                if ready[0]:
                    self._on_data(d_arr, _idx)

            self._logger.connect(idx, addr)
            self._refresh_card(idx, False, "Connexion…")
            try:
                async with BleakClient(addr) as client:
                    await asyncio.sleep(0.5)

                    def keepalive_ack_cb(*_):
                        notif_time[0] = time.monotonic()

                    try:
                        await client.start_notify(
                            "00000004-19ca-4651-86e5-fa29dcdd09d1", keepalive_ack_cb
                        )
                    except Exception:
                        pass

                    try:
                        await client.write_gatt_char(WRITE_UUID, RIDEON, response=False)
                    except Exception:
                        pass

                    try:
                        await asyncio.sleep(0.1)
                        await client.write_gatt_char(WRITE_UUID, UNLOCK_CMD, response=False)
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
                        self._refresh_card(idx, False, "Erreur notifications")
                        self._log(f"Aucune notif sur {addr} — reconnexion", "err")
                        break

                    self._refresh_card(idx, True, addr)
                    self._log(f"{label} connecté ({addr})", "ok")

                    battery = await self._read_battery(client)
                    if battery is not None:
                        self._update_battery(idx, battery)
                        self._log(f"{label} batterie : {battery}%", "dim")
                    else:
                        self._update_battery(idx, None)

                    self._btn_pressed[idx] = False
                    self._last_fire[idx]   = 0.0
                    notif_time[0]          = time.monotonic()
                    format_a_time[0]       = time.monotonic()
                    subscribe_time         = time.monotonic()
                    next_rssi_check        = subscribe_time + 5.0
                    ready[0]               = True
                    self._logger.ready(idx, addr)

                    next_keepalive = time.monotonic() + 2.0

                    while self._running and client.is_connected:
                        await asyncio.sleep(0.5)
                        now        = time.monotonic()
                        silence    = now - notif_time[0]
                        elapsed    = now - subscribe_time
                        fa_silence = now - format_a_time[0]

                        # Lock 24h Zwift
                        if elapsed > SILENCE_GRACE and fa_silence > LOCK_TIMEOUT:
                            lock_detected = True
                            break

                        # Watchdog silence
                        if elapsed > SILENCE_GRACE:
                            if silence > SILENCE_WARN:
                                self._logger.led_warn(idx, addr, silence)
                                self._update_status(idx,
                                    f"LED éteinte ({silence:.0f}s) — réveil…",
                                    _C["ora"])
                            else:
                                self._update_status(idx,
                                    f"Connecté  •  {short}",
                                    _C["cyan"])

                        # RSSI toutes les 5s
                        if now >= next_rssi_check:
                            try:
                                live_rssi = client.rssi
                                if live_rssi is not None:
                                    self._update_rssi(idx, live_rssi)
                            except Exception:
                                pass
                            next_rssi_check = now + 5.0

                        # Keepalive
                        if now >= next_keepalive:
                            try:
                                await client.write_gatt_char(WRITE_UUID, RIDEON, response=False)
                            except Exception:
                                pass
                            next_keepalive = now + KEEPALIVE_INTERVAL

                    for uuid in souscrit:
                        try:
                            await client.stop_notify(uuid)
                        except Exception:
                            pass

                    if lock_detected:
                        self._logger.disconnect(idx, addr, "lock_24h_reconnect")
                        self._update_status(idx, "Lock 24h — reconnexion…", _C["ora"])
                        self._log(f"{label} lock 24h Zwift — reconnexion automatique", "err")
                        self._clear_device_info(idx)
                        await asyncio.sleep(2.0)
                        format_a_time[0] = time.monotonic()
                        continue

                    self._logger.disconnect(idx, addr, "led_sleep_or_stop")
                    self._refresh_card(idx, False, "Déconnecté")
                    self._clear_device_info(idx)
                    self._log(f"Déconnecté : {addr}", "dim")
                    break

            except Exception as e:
                self._logger.disconnect(idx, addr, f"exception:{type(e).__name__}")
                self._refresh_card(idx, False, "Erreur")
                self._clear_device_info(idx)
                self._log(f"Erreur {addr}: {e}", "err")
                break

    async def _read_battery(self, client: BleakClient) -> int | None:
        try:
            data = await client.read_gatt_char(BATTERY_UUID)
            return int(data[0])
        except Exception:
            return None

    def _on_data(self, data: bytearray, idx: int):
        if not data or data[0] != 0x23 or len(data) < 5:
            return

        mask = data[3]
        addr = self._device_addrs[idx] or "?"

        if mask == 0xFF:
            self._btn_pressed[idx] = False
            if not any(self._btn_pressed):
                self._global_key = None
            self._logger.btn_release(idx, addr)
            return

        if not (mask & 0x20):
            key = TOUCHE_PLUS
        elif not (mask & 0x02):
            key = TOUCHE_MOINS
        else:
            return

        label = "▲  Vitesse +" if key == TOUCHE_PLUS else "▼  Vitesse −"

        with self._lock:
            if self._btn_pressed[idx]:
                self._logger.btn_block(idx, "state_machine", mask, addr)
                return

            now = time.monotonic()

            if (now - self._last_fire[idx]) < DEBOUNCE:
                self._logger.btn_block(idx, "debounce", mask, addr)
                return

            if key == self._global_key:
                self._btn_pressed[idx] = True
                self._logger.btn_block(idx, "global_dedup", mask, addr)
                return

            self._btn_pressed[idx] = True
            self._last_fire[idx]   = now
            self._global_key       = key
            if addr != "?" and not is_device_unlocked_24h(addr):
                _save_unlock_timestamp(addr)
            self._logger.btn_fire(idx, key, label, mask, addr)
            keyboard.type(key)

        self._fire_action(label)

    def _fire_action(self, label: str):
        self._count += 1
        self._count_lbl.setText(f"{self._count:04d}×")
        self._last_lbl.setText(label)
        self._last_lbl.setStyleSheet(
            f"color: {_C['cyan']}; font-family: Consolas; font-size: 9pt;"
            f" font-weight: bold; background: transparent;"
        )

    # ── MyWhoosh ──────────────────────────────────────────────

    def _launch_mywhoosh(self):
        app_id = "MyWhooshTechnologyService.644173E064ED2_eps1123pz0kt0!MYWHOOSH"
        try:
            subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"])
            self._log("MyWhoosh lancé automatiquement", "ok")
        except Exception as e:
            self._log(f"Impossible de lancer MyWhoosh : {e}", "err")

    # ── intervals.icu ─────────────────────────────────────────

    def _fetch_intervals(self):
        asyncio.ensure_future(self._fetch_intervals_coro())

    async def _fetch_intervals_coro(self):
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, self._intervals.fetch_all)
        self._update_perf(data)
        QTimer.singleShot(600_000, self._fetch_intervals)

    def _update_perf(self, data: dict):
        if not self._perf_lbl:
            return

        def bar(val, scale=100):
            if val is None:
                return "—"
            filled = min(5, max(0, round(val / (scale / 5))))
            return "▰" * filled + "▱" * (5 - filled)

        def tsb_color(tsb):
            if tsb is None:  return _C["ice3"]
            if tsb >   5:    return _C["cyan"]
            if tsb > -10:    return _C["cyand"]
            if tsb > -30:    return _C["ora"]
            return _C["red"]

        def tsb_label(tsb):
            if tsb is None:  return "—"
            if tsb >   5:    return f"+{tsb:.1f}  EN FORME"
            if tsb > -10:    return f"{tsb:.1f}  EQUILIBRE"
            if tsb > -30:    return f"{tsb:.1f}  FATIGUE"
            return               f"{tsb:.1f}  SURCHARGE"

        ctl = data.get("ctl")
        atl = data.get("atl")
        tsb = data.get("tsb")
        ftp = data.get("ftp")

        def _set(key, text, color):
            lbl = self._perf_lbl.get(key)
            if lbl:
                lbl.setText(text)
                lbl.setStyleSheet(
                    f"color: {color}; font-family: Consolas; font-size: 8pt;"
                    f" font-weight: bold; background: transparent;"
                )

        _set("ctl",
             f"{bar(ctl, 80)}  {ctl:.1f}" if ctl is not None else "—",
             _C["cyan"] if ctl else _C["ice3"])
        _set("atl",
             f"{bar(atl, 80)}  {atl:.1f}" if atl is not None else "—",
             _C["ora"] if atl else _C["ice3"])
        _set("tsb", tsb_label(tsb), tsb_color(tsb))
        _set("ftp",
             f"{ftp} W" if ftp else "— W  (calcul en cours)",
             _C["cyan"] if ftp else _C["ice3"])

        upd = self._perf_lbl.get("updated")
        if upd:
            upd.setText(f"MàJ {datetime.now().strftime('%H:%M')}")
            upd.setStyleSheet(
                f"color: {_C['ice3']}; font-family: Consolas; font-size: 6pt;"
                f" background: transparent;"
            )

    # ── UI helpers ────────────────────────────────────────────

    def _refresh_card(self, idx: int, connected: bool, status_text: str):
        if self._cards[idx]:
            self._cards[idx].set_connected(connected)
        lbl = self._status_lbl[idx]
        if lbl:
            color = _C["cyan"] if connected else _C["ice3"]
            lbl.setText(status_text)
            lbl.setStyleSheet(
                f"color: {color}; font-family: Consolas; font-size: 7pt;"
                f" background: transparent;"
            )

    def _update_status(self, idx: int, text: str, color: str):
        lbl = self._status_lbl[idx]
        if lbl:
            lbl.setText(text)
            lbl.setStyleSheet(
                f"color: {color}; font-family: Consolas; font-size: 7pt;"
                f" background: transparent;"
            )

    def _update_battery(self, idx: int, pct: int | None):
        lbl = self._battery_lbl[idx]
        if not lbl:
            return
        if pct is None:
            lbl.setText("BAT: —")
            lbl.setStyleSheet(
                f"color: {_C['ice3']}; font-family: Consolas; font-size: 7pt;"
                f" background: transparent;"
            )
        else:
            color  = battery_color(pct)
            filled = round(pct / 20)
            bar    = "▰" * filled + "▱" * (5 - filled)
            lbl.setText(f"▸{bar} {pct:3d}%")
            lbl.setStyleSheet(
                f"color: {color}; font-family: Consolas; font-size: 7pt;"
                f" background: transparent;"
            )

    def _update_rssi(self, idx: int, rssi: int):
        lbl = self._rssi_lbl[idx]
        if not lbl:
            return
        bars, color, _ = rssi_quality(rssi)
        lbl.setText(f"◈{bars}")
        lbl.setStyleSheet(
            f"color: {color}; font-family: Consolas; font-size: 7pt;"
            f" background: transparent;"
        )

    def _clear_device_info(self, idx: int):
        self._btn_pressed[idx] = False
        self._last_fire[idx]   = 0.0
        if not any(self._btn_pressed):
            self._global_key = None
        _dim = f"color: {_C['ice3']}; font-family: Consolas; font-size: 7pt; background: transparent;"
        if self._battery_lbl[idx]:
            self._battery_lbl[idx].setText("BAT: —")
            self._battery_lbl[idx].setStyleSheet(_dim)
        if self._rssi_lbl[idx]:
            self._rssi_lbl[idx].setText("SIG: —")
            self._rssi_lbl[idx].setStyleSheet(_dim)

    def _log(self, msg: str, tag: str = "dim"):
        colors = {
            "ok":  _C["cyan"],
            "err": _C["red"],
            "act": _C["ora"],
            "dim": _C["ice3"],
        }
        color = colors.get(tag, _C["ice3"])
        ts    = datetime.now().strftime("%H:%M:%S")

        cursor = self._log_box.textCursor()
        cursor.movePosition(QTextCursor.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(f"[{ts}] {msg}\n", fmt)

        self._log_box.setTextCursor(cursor)
        self._log_box.ensureCursorVisible()


# ── Point d'entrée ────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = App()
    window.show()

    with loop:
        loop.run_forever()
