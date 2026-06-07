@echo off
title Zwift Click → MyWhoosh
echo Installation des dependances si necessaire...
pip install bleak pynput PySide6 qasync --quiet
if errorlevel 1 (
    echo.
    echo Impossible d'installer les dependances.
    echo Verifiez votre connexion Internet puis relancez Lancer.bat.
    pause
    exit /b 1
)
echo Lancement de l'application...
echo Gardez cette fenetre ouverte pendant l'utilisation.
echo Elle se fermera automatiquement quand l'application sera fermee.
python interface.py
if errorlevel 1 (
    echo.
    echo L'application s'est arretee avec une erreur.
    echo Verifiez que Python est installe et relancez Lancer.bat.
    pause
    exit /b 1
)
