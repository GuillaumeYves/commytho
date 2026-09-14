"""Planificateur macOS, via un agent launchd de session.

L'agent est posé dans ~/Library/LaunchAgents, donc il tourne sous votre session
utilisateur, sans droits administrateur, et repart tout seul après un
redémarrage.
"""

from __future__ import annotations

import os
import plistlib
from pathlib import Path

from .. import paths
from .base import Scheduler, run, tick_command

LABEL = "com.commytho.tick"


def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _domain() -> str:
    return f"gui/{os.getuid()}"


class LaunchdScheduler(Scheduler):
    kind = "launchd"

    def install(self, tick_minutes: int) -> str:
        paths.ensure_dirs()
        journal = paths.data_dir() / "scheduler.log"
        contenu = {
            "Label": LABEL,
            "ProgramArguments": tick_command(),
            "StartInterval": tick_minutes * 60,
            "RunAtLoad": False,
            "StandardOutPath": str(journal),
            "StandardErrorPath": str(journal),
            # launchd hérite d'un PATH minimal. commytho appelle git, donc on
            # lui donne les emplacements habituels, Homebrew compris.
            "EnvironmentVariables": {
                "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
            },
        }

        chemin = _plist_path()
        chemin.parent.mkdir(parents=True, exist_ok=True)
        self.uninstall()
        with chemin.open("wb") as fichier:
            plistlib.dump(contenu, fichier)

        resultat = run(["launchctl", "bootstrap", _domain(), str(chemin)], check=False)
        if resultat.returncode != 0:
            # bootstrap n'existe que depuis macOS 10.11. On garde la vieille
            # méthode en secours, elle reste acceptée.
            run(["launchctl", "load", "-w", str(chemin)])
        return LABEL

    def uninstall(self) -> bool:
        chemin = _plist_path()
        existait = chemin.exists()
        run(["launchctl", "bootout", f"{_domain()}/{LABEL}"], check=False)
        run(["launchctl", "unload", str(chemin)], check=False)
        if existait:
            chemin.unlink()
        return existait

    def status(self) -> str | None:
        if not _plist_path().exists():
            return None
        resultat = run(["launchctl", "print", f"{_domain()}/{LABEL}"], check=False)
        etat = "chargé" if resultat.returncode == 0 else "installé mais non chargé"
        return f"agent launchd {LABEL} ({etat})"
