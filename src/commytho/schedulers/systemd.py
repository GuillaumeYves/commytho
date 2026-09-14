"""Planificateurs Linux : minuterie systemd utilisateur, ou cron en secours.

On préfère systemd quand il est là. Il rattrape les réveils manqués pendant une
mise en veille, il journalise, et il se retire proprement. Sur une machine sans
systemd, un simple crontab fait le travail.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .. import paths
from .base import Scheduler, SchedulerError, run, tick_command

UNIT = "commytho"
CRON_MARKER = "# commytho"


def pick_unix_scheduler() -> Scheduler:
    """Choisit systemd si disponible, sinon cron."""
    if shutil.which("systemctl"):
        return SystemdScheduler()
    if shutil.which("crontab"):
        return CronScheduler()
    raise SchedulerError(
        "Ni systemctl ni crontab n'ont été trouvés. Installez l'un des deux, "
        "ou lancez commytho run vous-même depuis votre propre planificateur."
    )


def _unit_dir() -> Path:
    return Path.home() / ".config" / "systemd" / "user"


class SystemdScheduler(Scheduler):
    kind = "systemd"

    def install(self, tick_minutes: int) -> str:
        paths.ensure_dirs()
        dossier = _unit_dir()
        dossier.mkdir(parents=True, exist_ok=True)
        commande = " ".join(tick_command())

        service = (
            "[Unit]\n"
            "Description=Reveil commytho\n"
            "\n"
            "[Service]\n"
            "Type=oneshot\n"
            f"ExecStart={commande}\n"
        )
        minuterie = (
            "[Unit]\n"
            "Description=Reveil commytho toutes les "
            f"{tick_minutes} minutes\n"
            "\n"
            "[Timer]\n"
            f"OnBootSec={tick_minutes}min\n"
            f"OnUnitActiveSec={tick_minutes}min\n"
            # Persistent rattrape le réveil manqué si la machine était éteinte.
            "Persistent=true\n"
            "AccuracySec=1min\n"
            "\n"
            "[Install]\n"
            "WantedBy=timers.target\n"
        )
        (dossier / f"{UNIT}.service").write_text(service, encoding="utf-8")
        (dossier / f"{UNIT}.timer").write_text(minuterie, encoding="utf-8")

        run(["systemctl", "--user", "daemon-reload"])
        run(["systemctl", "--user", "enable", "--now", f"{UNIT}.timer"])
        return f"{UNIT}.timer"

    def uninstall(self) -> bool:
        dossier = _unit_dir()
        fichiers = [dossier / f"{UNIT}.timer", dossier / f"{UNIT}.service"]
        existait = any(f.exists() for f in fichiers)
        run(["systemctl", "--user", "disable", "--now", f"{UNIT}.timer"], check=False)
        for fichier in fichiers:
            if fichier.exists():
                fichier.unlink()
        run(["systemctl", "--user", "daemon-reload"], check=False)
        return existait

    def status(self) -> str | None:
        if not (_unit_dir() / f"{UNIT}.timer").exists():
            return None
        resultat = run(
            ["systemctl", "--user", "list-timers", "--no-pager", f"{UNIT}.timer"], check=False
        )
        actif = "actif" if f"{UNIT}.timer" in resultat.stdout else "inactif"
        return f"minuterie systemd {UNIT}.timer ({actif})"


class CronScheduler(Scheduler):
    """Secours pour les machines sans systemd.

    Les lignes posées par commytho portent un marqueur en fin de ligne, ce qui
    permet de les retirer sans toucher au reste du crontab.
    """

    kind = "cron"

    def install(self, tick_minutes: int) -> str:
        commande = " ".join(tick_command())
        if tick_minutes >= 60:
            heures = max(1, tick_minutes // 60)
            planning = f"0 */{heures} * * *"
        else:
            planning = f"*/{max(1, tick_minutes)} * * * *"

        lignes = self._lignes_hors_commytho()
        lignes.append(f"{planning} {commande} {CRON_MARKER}")
        self._ecrire(lignes)
        return planning

    def uninstall(self) -> bool:
        actuelles = self._lignes_actuelles()
        restantes = [ligne for ligne in actuelles if CRON_MARKER not in ligne]
        if len(restantes) == len(actuelles):
            return False
        self._ecrire(restantes)
        return True

    def status(self) -> str | None:
        for ligne in self._lignes_actuelles():
            if CRON_MARKER in ligne:
                return f"entrée cron : {ligne}"
        return None

    def _lignes_actuelles(self) -> list[str]:
        resultat = run(["crontab", "-l"], check=False)
        if resultat.returncode != 0:
            # Pas de crontab pour cet utilisateur, ce qui n'est pas une erreur.
            return []
        return [ligne for ligne in resultat.stdout.splitlines() if ligne.strip()]

    def _lignes_hors_commytho(self) -> list[str]:
        return [ligne for ligne in self._lignes_actuelles() if CRON_MARKER not in ligne]

    def _ecrire(self, lignes: list[str]) -> None:
        import subprocess

        contenu = "\n".join(lignes) + "\n"
        resultat = subprocess.run(  # noqa: S603 - crontab lit son entrée standard
            ["crontab", "-"], input=contenu, text=True, capture_output=True
        )
        if resultat.returncode != 0:
            raise SchedulerError(f"crontab a refusé la mise à jour : {resultat.stderr.strip()}")
