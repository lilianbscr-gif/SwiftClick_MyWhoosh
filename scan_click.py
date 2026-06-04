"""
scan_click.py
-------------
Script de scan Bluetooth pour trouver vos Zwift Click.
Exécutez ce script en premier pour récupérer les adresses MAC de vos appareils.

Usage : python scan_click.py
"""

import asyncio
from bleak import BleakScanner


async def scan():
    print("🔍 Scan Bluetooth en cours (10 secondes)...")
    print("   → Appuyez sur un bouton de votre Zwift Click pour l'activer (LED bleue clignotante)\n")

    # discover() retourne des tuples (BLEDevice, AdvertisementData)
    results = await BleakScanner.discover(timeout=10.0, return_adv=True)

    zwift_devices = []
    autres_devices = []

    for address, (device, adv_data) in results.items():
        name = device.name or "inconnu"
        if "zwift" in name.lower() or "click" in name.lower():
            zwift_devices.append((device, adv_data))
        else:
            autres_devices.append((device, adv_data))

    if zwift_devices:
        print("✅ Appareils Zwift détectés :")
        for device, adv_data in zwift_devices:
            print(f"   Nom         : {device.name}")
            print(f"   Adresse MAC : {device.address}")
            print(f"   Signal RSSI : {adv_data.rssi} dBm")
            print()
    else:
        print("❌ Aucun appareil Zwift trouvé.")
        print("   Assurez-vous que votre Click est en mode connexion (LED bleue clignotante).")
        print("   Appuyez sur un bouton pour le réveiller, puis relancez ce script.\n")

    if autres_devices:
        print(f"📡 Autres appareils BLE détectés ({len(autres_devices)}) :")
        for device, adv_data in autres_devices:
            print(f"   {device.name or 'inconnu'} — {device.address}")


asyncio.run(scan())
