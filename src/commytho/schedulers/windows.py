"""Planificateur Windows, via une tâche planifiée utilisateur.

schtasks.exe est présent sur toutes les éditions de Windows, y compris les
Familiales, contrairement aux applets PowerShell de planification. La tâche est
posée pour l'utilisateur courant, sans élévation.
"""

from __future__ import annotations

from .base import Scheduler, run, tick_command

TASK_NAME = "commytho"


def _ligne_de_commande() -> str:
    """Assemble la valeur passée à /TR.

    schtasks attend une chaîne unique. Les chemins contenant des espaces, cas
    banal sous Windows, doivent donc être entourés de guillemets à l'intérieur
    de cette chaîne.
    """
    executable, *arguments = tick_command()
    return " ".join([f'"{executable}"', *arguments])


class WindowsScheduler(Scheduler):
    kind = "schtasks"

    def install(self, tick_minutes: int) -> str:
        # schtasks plafonne /MO à 1439 minutes pour une planification MINUTE.
        minutes = max(1, min(tick_minutes, 1439))
        run(
            [
                "schtasks",
                "/Create",
                "/TN",
                TASK_NAME,
                "/TR",
                _ligne_de_commande(),
                "/SC",
                "MINUTE",
                "/MO",
                str(minutes),
                # /F remplace une tâche existante, ce qui rend la commande up
                # rejouable sans avoir à passer par down.
                "/F",
            ]
        )
        return TASK_NAME

    def uninstall(self) -> bool:
        resultat = run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], check=False)
        return resultat.returncode == 0

    def status(self) -> str | None:
        resultat = run(["schtasks", "/Query", "/TN", TASK_NAME], check=False)
        if resultat.returncode != 0:
            return None
        return f"tâche planifiée Windows : {TASK_NAME}"
