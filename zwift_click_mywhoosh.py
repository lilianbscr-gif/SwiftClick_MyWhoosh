"""
zwift_click_mywhoosh.py
-----------------------
Connecte vos Zwift Click à MyWhoosh via simulation de touches clavier.

Protocole BLE des Zwift Click (ingénierie inverse par la communauté) :
  - Service UUID  : 00000001-19ca-4651-86e5-fa29dcdd09d1
  - Notification  : 00000002-19ca-4651-86e5-fa29dcdd09d1
  - Control Point : 00000003-19ca-4651-86e5-fa29dcdd09d1

Touches simulées vers MyWhoosh (par défaut) :
  - Bouton +  (haut) → touche F3  (vitesse +)
  - Bouton -  (bas)  → touche F4  (vitesse -)

Vous pouvez modifier les touches dans la section CONFIGURATION ci-dessous.

Usage :
  python zwift_click_mywhoosh.py
  python zwift_click_mywhoosh.py --mac AA:BB:CC:DD:EE:FF

Prérequis :
  pip install bleak pynput
"""

import asyncio
import argparse
import logging
from datetime import datetime

from bleak import BleakClient, BleakScanner
from pynput.keyboard import Key, Controller

# ============================================================
# CONFIGURATION — modifiez ici les touches selon votre besoin
# ============================================================

# Touches envoyées à MyWhoosh lors d'un appui
TOUCHE_PLUS  = Key.f3   # Vitesse +  (shift up)
TOUCHE_MOINS = Key.f4   # Vitesse -  (shift down)

# Délai anti-rebond en secondes (évite les doubles appuis)
DEBOUNCE = 0.3
KEEPALIVE_INTERVAL = 15.0

# ============================================================
# UUIDs du protocole Zwift Click (ne pas modifier)
# ============================================================

SERVICE_UUID      = "00000001-19ca-4651-86e5-fa29dcdd09d1"
NOTIF_UUID        = "00000002-19ca-4651-86e5-fa29dcdd09d1"
CTRL_UUID         = "00000003-19ca-4651-86e5-fa29dcdd09d1"
RIDEON            = b"RideOn"

# Manufacturer ID Zwift dans les données d'advertisement
ZWIFT_MANUFACTURER_ID = 0x094A

# Codes boutons dans le message BLE (octet de type bouton)
# Valeurs connues : 0x11 = bouton + pressé, 0x12 = bouton - pressé
# 0x15 = message d'idle (heartbeat toutes les ~1 sec)
BTN_PLUS_PRESSED  = 0x11
BTN_MINUS_PRESSED = 0x12
MSG_IDLE          = 0x15

# ============================================================

keyboard = Controller()
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

last_action_time = 0.0


def log_demarrage():
    print("=" * 55)
    print("  Zwift Click → MyWhoosh  |  Démarré le", datetime.now().strftime("%d/%m/%Y %H:%M"))
    print("=" * 55)
    print(f"  Bouton +  →  {TOUCHE_PLUS}")
    print(f"  Bouton -  →  {TOUCHE_MOINS}")
    print("  Appuyez Ctrl+C pour arrêter")
    print("=" * 55)
    print()


def handle_notification(sender, data: bytearray):
    """Appelée à chaque notification BLE reçue du Click."""
    global last_action_time

    if not data:
        return

    msg_type = data[0]

    # Ignorer les messages d'idle
    if msg_type == MSG_IDLE:
        return

    now = asyncio.get_event_loop().time()

    # Anti-rebond
    if (now - last_action_time) < DEBOUNCE:
        return

    if msg_type == BTN_PLUS_PRESSED:
        log.info("▲  Bouton +  →  Vitesse +")
        keyboard.press(TOUCHE_PLUS)
        keyboard.release(TOUCHE_PLUS)
        last_action_time = now

    elif msg_type == BTN_MINUS_PRESSED:
        log.info("▼  Bouton -  →  Vitesse -")
        keyboard.press(TOUCHE_MOINS)
        keyboard.release(TOUCHE_MOINS)
        last_action_time = now

    else:
        # Message inconnu — affiché pour vous aider à cartographier d'autres boutons
        log.debug(f"Message inconnu : {data.hex()}")


async def trouver_click(mac_cible=None):
    """Scan BLE et retourne le premier Zwift Click trouvé."""
    log.info("Scan Bluetooth en cours...")
    log.info("→ Appuyez sur un bouton de votre Zwift Click pour l'activer (LED bleue)\n")

    def est_un_click(device, adv_data):
        name = (device.name or "").lower()
        if mac_cible and device.address.upper() != mac_cible.upper():
            return False
        if "zwift" in name or "click" in name:
            return True
        # Détecter via le Manufacturer ID Zwift
        mfr = adv_data.manufacturer_data or {}
        return ZWIFT_MANUFACTURER_ID in mfr

    device = await BleakScanner.find_device_by_filter(est_un_click, timeout=30.0)

    if device is None:
        log.error("Aucun Zwift Click trouvé après 30 secondes.")
        log.error("→ Vérifiez que le Bluetooth est activé sur votre PC.")
        log.error("→ Appuyez sur un bouton du Click pour le réveiller.")
        return None

    log.info(f"✅ Click trouvé : {device.name} ({device.address})")
    return device


async def connecter_et_ecouter(mac_cible=None):
    """Connexion au Click et écoute des notifications."""
    device = await trouver_click(mac_cible)
    if device is None:
        return

    log.info(f"Connexion à {device.address}...")

    async with BleakClient(device.address) as client:
        if not client.is_connected:
            log.error("Échec de la connexion.")
            return

        log.info("✅ Connecté ! En attente des pressions de boutons...\n")

        try:
            await client.write_gatt_char(CTRL_UUID, RIDEON, response=False)
            log.debug("Keep-alive initial envoyé.")
        except Exception as e:
            log.debug(f"Keep-alive initial ignoré : {e}")

        # S'abonner aux notifications BLE
        await client.start_notify(NOTIF_UUID, handle_notification)

        # Boucle infinie — reste connecté jusqu'à Ctrl+C
        try:
            next_keepalive = asyncio.get_event_loop().time() + KEEPALIVE_INTERVAL
            while True:
                await asyncio.sleep(1)
                now = asyncio.get_event_loop().time()
                if now < next_keepalive:
                    continue

                try:
                    await client.write_gatt_char(CTRL_UUID, RIDEON, response=False)
                    next_keepalive = now + KEEPALIVE_INTERVAL
                    log.debug("Keep-alive envoyé.")
                except Exception as e:
                    log.warning(f"Keep-alive perdu : {e}")
                    break
        except asyncio.CancelledError:
            pass
        finally:
            await client.stop_notify(NOTIF_UUID)
            log.info("Déconnecté du Click.")


async def main(mac_cible=None):
    log_demarrage()
    while True:
        try:
            await connecter_et_ecouter(mac_cible)
        except Exception as e:
            log.warning(f"Connexion perdue : {e}")
            log.info("Reconnexion dans 3 secondes...")
            await asyncio.sleep(3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zwift Click → MyWhoosh bridge")
    parser.add_argument("--mac", help="Adresse MAC du Zwift Click (optionnel)", default=None)
    parser.add_argument("-v", "--verbose", action="store_true", help="Mode verbeux")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        asyncio.run(main(mac_cible=args.mac))
    except KeyboardInterrupt:
        print("\n👋 Script arrêté.")
