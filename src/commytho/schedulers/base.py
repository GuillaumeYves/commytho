"""Contrat commun aux planificateurs, et construction de la commande de réveil."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ..console import NO_WINDOW


class SchedulerError(Exception):
    """La pose ou le retrait de la tâche a échoué."""


class Scheduler:
    """Interface minimale attendue par la commande up et la commande down."""

    kind = "inconnu"

    def install(self, tick_minutes: int) -> str:
        """Pose la tâche et renvoie son identifiant sur le système."""
        raise NotImplementedError

    def uninstall(self) -> bool:
        """Retire la tâche. Renvoie False si elle n'existait pas."""
        raise NotImplementedError

    def status(self) -> str | None:
        """Décrit la tâche posée, ou None s'il n'y en a pas."""
        raise NotImplementedError


def python_executable() -> str:
    """Interpréteur à utiliser pour les réveils.

    Sous Windows, pythonw.exe évite qu'une fenêtre de console apparaisse
    toutes les demi-heures. Ailleurs, sys.executable convient tel quel. Dans
    les deux cas le chemin est absolu et pointe vers l'environnement où
    commytho est installé, donc la variable PATH de la tâche n'a pas
    d'importance.
    """
    executable = Path(sys.executable)
    if sys.platform == "win32":
        sans_console = executable.with_name("pythonw.exe")
        if sans_console.exists():
            return str(sans_console)
    return str(executable)


def tick_command() -> list[str]:
    """Commande exécutée à chaque réveil."""
    return [python_executable(), "-m", "commytho", "run"]


def run(commande: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    """Petit utilitaire partagé pour appeler les outils du système."""
    resultat = subprocess.run(  # noqa: S603 - arguments construits par nos soins
        commande,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=NO_WINDOW,
    )
    if check and resultat.returncode != 0:
        sortie = (resultat.stderr or resultat.stdout or "").strip()
        raise SchedulerError(f"{commande[0]} a échoué : {sortie}")
    return resultat
