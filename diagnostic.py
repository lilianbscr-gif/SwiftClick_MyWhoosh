"""
diagnostic.py
-------------
Script de diagnostic brut — explore tous les services et caractéristiques
du Zwift Click et tente de recevoir des notifications sur toutes les
caractéristiques disponibles.

Utilise la même commande d'activation que l'interface (b"RideOn" sur 00000003)
pour reproduire exactement les conditions de production.

Usage : python diagnostic.py
"""

import asyncio
from datetime import datetime
from bleak import BleakClient, BleakScanner

ZWIFT_MFR_ID = 0x094A
WRITE_UUID   = "00000003-19ca-4651-86e5-fa29dcdd09d1"
RIDEON       = b"RideOn"


def afficher_donnees(char_uuid, data: bytearray):
    ts  = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    dec = list(data)
    hex_str = data.hex()

    # Décodage du format pour aider au diagnostic
    hint = ""
    first = data[0] if data else None

    if len(data) >= 5 and first == 0x23:
        mask = data[3]
        if not (mask & 0x20):
            hint = "  ← FORMAT A : BOUTON +"
        elif not (mask & 0x02):
            hint = "  ← FORMAT A : BOUTON −"
        elif mask == 0xFF:
            hint = "  ← FORMAT A : idle"
        else:
            hint = f"  ← FORMAT A : mask=0x{mask:02x}"
    elif first == 0x11:
        hint = "  ← FORMAT B : BOUTON +"
    elif first == 0x12:
        hint = "  ← FORMAT B : BOUTON −"
    elif first == 0x15:
        hint = "  ← FORMAT B : heartbeat"
    elif len(data) == 2 and first == 0x01:
        btn = data[1]
        direction = "BOUTON −" if (btn & 0x04) else "BOUTON +"
        hint = f"  ← FORMAT C : {direction} (pressé, button_id=0x{btn:02x})"
    elif len(data) == 2 and first == 0x04:
        hint = f"  ← FORMAT C : relâché (button_id=0x{data[1]:02x})"
    elif len(data) == 1 and first == 0x50:
        hint = "  ← Batterie 80%"
    elif char_uuid.startswith("00002a19"):
        hint = f"  ← Batterie {data[0]}%"

    print(f"[{ts}] [{char_uuid[:8]}...] {hex_str}  {dec}{hint}")


async def diagnostic():
    print("=" * 60)
    print("  Diagnostic Zwift Click  (mode production — RideOn)")
    print("=" * 60)
    print("Scan en cours... (appuyez sur un bouton du Click)\n")

    def est_click(device, adv):
        name = (device.name or "").lower()
        mfr = adv.manufacturer_data or {}
        return "zwift" in name or "click" in name or "sf2" in name or ZWIFT_MFR_ID in mfr

    device = await BleakScanner.find_device_by_filter(est_click, timeout=30.0)
    if device is None:
        print("Aucun Click trouvé.")
        return

    print(f"Trouvé : {device.name or '(sans nom)'}  ({device.address})\n")

    async with BleakClient(device.address) as client:
        print("Connecté !\n")

        # Lister tous les services
        print("Services et caractéristiques :")
        all_notify_uuids = []
        all_write_uuids  = []

        for service in client.services:
            print(f"\n  Service : {service.uuid}")
            for char in service.characteristics:
                props = ", ".join(char.properties)
                print(f"    Caract. : {char.uuid}  [{props}]")
                if "notify" in char.properties or "indicate" in char.properties:
                    all_notify_uuids.append(char.uuid)
                if "write" in char.properties or "write-without-response" in char.properties:
                    all_write_uuids.append(char.uuid)

        # Lire la batterie si disponible
        BATTERY_UUID = "00002a19-0000-1000-8000-00805f9b34fb"
        try:
            bat_data = await client.read_gatt_char(BATTERY_UUID)
            print(f"\nBatterie : {bat_data[0]}%")
        except Exception:
            pass

        # Envoyer RideOn (identique à l'interface) pour activer le bon mode
        print(f"\nEnvoi de RideOn sur {WRITE_UUID[:8]}... (commande d'activation production)")
        try:
            await client.write_gatt_char(WRITE_UUID, RIDEON, response=False)
            print("  OK")
        except Exception as e:
            print(f"  Echec : {e}")

        # Souscrire à toutes les caractéristiques notifiables
        print(f"\nSouscription aux notifications ({len(all_notify_uuids)} caractéristiques)...")
        for uuid in all_notify_uuids:
            try:
                await client.start_notify(
                    uuid,
                    lambda _, d, u=uuid: afficher_donnees(u, d)
                )
                print(f"  OK : {uuid}")
            except Exception as e:
                print(f"  Echec {uuid[:8]}... : {e}")

        print("\n--- Appuyez sur les boutons maintenant (30 secondes) ---\n")
        await asyncio.sleep(30)

        print("\nDiagnostic terminé.")
        for uuid in all_notify_uuids:
            try:
                await client.stop_notify(uuid)
            except Exception:
                pass


asyncio.run(diagnostic())
