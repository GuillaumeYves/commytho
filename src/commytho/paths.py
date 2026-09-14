"""Emplacements des fichiers de commytho, selon la plateforme.

On suit les conventions de chaque OS plutôt que de tout entasser dans ~/.commytho :
les sauvegardes de profil et les outils de nettoyage savent quoi faire de ces dossiers.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "commytho"


def _home() -> Path:
    return Path.home()


def config_dir() -> Path:
    """Dossier de la configuration (petit, stable, sauvegardable)."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(_home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME
    if sys.platform == "darwin":
        return _home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_CONFIG_HOME") or str(_home() / ".config")
    return Path(base) / APP_NAME


def data_dir() -> Path:
    """Dossier des données de travail : état du jour, journaux, dépôt cloné."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(_home() / "AppData" / "Local")
        return Path(base) / APP_NAME
    if sys.platform == "darwin":
        return _home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_DATA_HOME") or str(_home() / ".local" / "share")
    return Path(base) / APP_NAME


def config_file() -> Path:
    return config_dir() / "config.json"


def state_file() -> Path:
    return data_dir() / "state.json"


def log_file() -> Path:
    return data_dir() / "commytho.log"


def checkout_dir() -> Path:
    """Copie locale du dépôt cible, gérée entièrement par commytho."""
    return data_dir() / "checkout"


def ensure_dirs() -> None:
    """Crée les dossiers manquants. Idempotent, appelé avant toute écriture."""
    for directory in (config_dir(), data_dir()):
        directory.mkdir(parents=True, exist_ok=True)
