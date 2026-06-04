# Zwift Click → MyWhoosh  |  Guide d'utilisation

## Contenu du dossier

| Fichier                     | Rôle                                              |
|-----------------------------|---------------------------------------------------|
| `Lancer.bat`                | ⭐ Double-cliquez ici pour tout démarrer           |
| `interface.py`              | Application graphique principale                  |
| `zwift_click_mywhoosh.py`   | Script en ligne de commande (version avancée)     |
| `scan_click.py`             | Scan Bluetooth pour trouver vos appareils         |

---

## Démarrage rapide

1. **Double-cliquez sur `Lancer.bat`**
2. Une fenêtre s'ouvre — cliquez sur **"Connecter le Zwift Click"**
3. Appuyez sur un bouton de votre Zwift Click (LED bleue clignotante)
4. L'application détecte automatiquement votre Click et se connecte
5. Lancez MyWhoosh — les boutons fonctionnent !

---

## Touches configurées par défaut

| Bouton Click | Touche envoyée | Action dans MyWhoosh |
|--------------|----------------|----------------------|
| Bouton  +    |  i             | Vitesse +            |
| Bouton  -    |  k             | Vitesse -            |

Pour changer les touches, ouvrez `interface.py` avec le Bloc-notes
et modifiez les lignes suivantes en haut du fichier :

```python
TOUCHE_PLUS  = "i"   # ← changez i par autre chose
TOUCHE_MOINS = "k"  # ← changez k par autre chose
```

Exemples de touches disponibles :
- `Key.f1` à `Key.f12`  →  touches de fonction
- `Key.up`, `Key.down`  →  flèches haut/bas
- `Key.page_up`, `Key.page_down`

---

## Prérequis

- Windows 10/11 avec Bluetooth activé
- Python 3.8+ installé (python.org)
- Bibliothèques : `pip install bleak pynput`
  (installées automatiquement par `Lancer.bat`)

---

## Dépannage

**"Aucun Click trouvé"**
→ Appuyez sur un bouton du Click pour le réveiller (LED bleue)
→ Vérifiez que le Bluetooth est activé dans Windows

**Les boutons sont détectés mais rien ne se passe dans MyWhoosh**
→ Assurez-vous que MyWhoosh est la fenêtre active (cliquez dessus)
→ Vérifiez que le "Virtual Shifting" est activé dans MyWhoosh
→ Les touches i/k sont peut-être différentes dans votre version de MyWhoosh

**Reconnexion automatique**
→ Si le Click se déconnecte, l'application reconnecte automatiquement
