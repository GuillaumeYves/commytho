"""Stockage du jeton GitHub.

Le jeton part dans le trousseau du système : Gestionnaire d'identification sous
Windows, Trousseau d'accès sous macOS, Secret Service sous Linux. Il ne transite
jamais par la configuration, ni par la ligne de commande, ni par un dépôt.

Sur une machine sans trousseau disponible, typiquement un serveur Linux sans
session graphique, on se rabat sur un fichier lisible par le seul propriétaire.
C'est moins bon, donc commytho le dit clairement au moment de la connexion.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from . import paths

SERVICE = "commytho"
ACCOUNT = "github-token"

# Nom de la variable d'environnement lue en priorité. Pratique pour les tests
# et pour les machines où l'on ne veut rien écrire sur disque.
ENV_VAR = "COMMYTHO_TOKEN"


class AuthError(Exception):
    """Aucun jeton utilisable, ou trousseau inaccessible."""


def _fallback_file() -> Path:
    return paths.config_dir() / "token"


def _keyring():
    """Importe keyring à la demande.

    L'import déclenche la détection du backend, qui peut être lente ou lever
    une exception sur une machine mal configurée. On ne le paie donc que
    lorsqu'on touche vraiment au jeton.
    """
    try:
        import keyring

        return keyring
    except Exception:  # noqa: BLE001 - backend indisponible, on se rabat sur le fichier
        return None


def store(token: str) -> str:
    """Enregistre le jeton et renvoie le mode de stockage retenu."""
    kr = _keyring()
    if kr is not None:
        try:
            kr.set_password(SERVICE, ACCOUNT, token)
            return "trousseau"
        except Exception:  # noqa: BLE001 - pas de backend utilisable
            pass

    paths.ensure_dirs()
    chemin = _fallback_file()
    chemin.write_text(token, encoding="utf-8")
    if os.name != "nt":
        chemin.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return "fichier"


def retrieve() -> str:
    """Renvoie le jeton, ou lève AuthError s'il n'y en a pas."""
    depuis_env = os.environ.get(ENV_VAR)
    if depuis_env:
        return depuis_env.strip()

    kr = _keyring()
    if kr is not None:
        try:
            token = kr.get_password(SERVICE, ACCOUNT)
            if token:
                return token
        except Exception:  # noqa: BLE001 - trousseau verrouillé ou absent
            pass

    chemin = _fallback_file()
    if chemin.exists():
        token = chemin.read_text(encoding="utf-8").strip()
        if token:
            return token

    raise AuthError("Aucun jeton enregistré. Lancez d'abord : commytho login")


def forget() -> bool:
    """Efface le jeton partout où il pourrait se trouver."""
    efface = False
    kr = _keyring()
    if kr is not None:
        try:
            kr.delete_password(SERVICE, ACCOUNT)
            efface = True
        except Exception:  # noqa: BLE001 - rien à supprimer
            pass
    chemin = _fallback_file()
    if chemin.exists():
        chemin.unlink()
        efface = True
    return efface


def has_token() -> bool:
    try:
        retrieve()
        return True
    except AuthError:
        return False
