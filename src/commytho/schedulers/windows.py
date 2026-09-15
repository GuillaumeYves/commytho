"""Planificateur Windows, via une tâche planifiée utilisateur.

schtasks.exe est présent sur toutes les éditions de Windows, y compris les
Familiales, contrairement aux applets PowerShell de planification. La tâche est
posée pour l'utilisateur courant, sans élévation.

La tâche est décrite par un fichier XML plutôt que par les options en ligne de
commande de /Create : c'est le seul moyen, en restant sur schtasks, de désarmer
les réglages de batterie. Par défaut Windows refuse de démarrer une tâche quand
la machine est sur batterie, et l'arrête si elle y passe en cours de route. Sur
un portable débranché, cela veut dire zéro commit, sans le moindre message.

La tâche porte deux déclencheurs : la répétition régulière, et l'ouverture de
session. Le second sert au rattrapage : à l'allumage de la machine, commytho
regarde le programme du jour sans attendre le prochain réveil périodique.

La tâche est marquée masquée et l'action pointe pythonw.exe, qui n'ouvre pas de
console. Les processus git lancés ensuite le sont sans fenêtre non plus, voir
le module console : sans cela, chaque commit ferait clignoter une fenêtre noire
au premier plan et volerait le focus de la fenêtre en cours.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

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


def _utilisateur() -> str:
    """Compte sous lequel la tâche tournera, au format attendu par le XML.

    Le domaine compte : sur un poste joint à Entra ID le nom seul ne suffit pas
    à identifier le compte.
    """
    nom = os.environ.get("USERNAME", "")
    domaine = os.environ.get("USERDOMAIN", "")
    return f"{domaine}\\{nom}" if domaine and nom else nom


def _definition_xml(tick_minutes: int) -> str:
    """Décrit la tâche complète, réglages de batterie compris."""
    executable, *arguments = tick_command()
    debut = datetime.now().replace(second=0, microsecond=0).isoformat()
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Date>{debut}</Date>
    <Description>Commits planifiés par commytho.</Description>
  </RegistrationInfo>
  <Principals>
    <Principal id="Author">
      <UserId>{escape(_utilisateur())}</UserId>
      <LogonType>InteractiveToken</LogonType>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <Enabled>true</Enabled>
    <Hidden>true</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
  </Settings>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{escape(_utilisateur())}</UserId>
      <Delay>PT1M</Delay>
    </LogonTrigger>
    <TimeTrigger>
      <StartBoundary>{debut}</StartBoundary>
      <Enabled>true</Enabled>
      <Repetition>
        <Interval>PT{tick_minutes}M</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
    </TimeTrigger>
  </Triggers>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(executable)}</Command>
      <Arguments>{escape(" ".join(arguments))}</Arguments>
    </Exec>
  </Actions>
</Task>
"""


def _pose_par_xml(tick_minutes: int) -> bool:
    """Tente la pose par fichier XML. Renvoie False si schtasks l'a refusé."""
    # schtasks lit le fichier en UTF-16 : en UTF-8 il rejette la définition
    # avec un message qui parle de format, sans plus de précision.
    fichier = Path(tempfile.gettempdir()) / f"commytho-{os.getpid()}.xml"
    fichier.write_text(_definition_xml(tick_minutes), encoding="utf-16")
    try:
        resultat = run(
            ["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(fichier), "/F"],
            check=False,
        )
        return resultat.returncode == 0
    finally:
        fichier.unlink(missing_ok=True)


class WindowsScheduler(Scheduler):
    kind = "schtasks"

    def install(self, tick_minutes: int) -> str:
        # schtasks plafonne /MO à 1439 minutes pour une planification MINUTE.
        minutes = max(1, min(tick_minutes, 1439))
        if _pose_par_xml(minutes):
            return TASK_NAME
        # Repli sur les options en ligne de commande. La tâche obtenue ne
        # tournera pas sur batterie, mais mieux vaut une tâche bridée que pas
        # de tâche du tout si une version de Windows boude notre XML.
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
