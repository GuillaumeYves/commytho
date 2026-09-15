"""Lancement des processus enfants sans fenêtre de console sous Windows.

La tâche planifiée appelle déjà pythonw.exe, qui n'ouvre pas de console. Mais
un processus sans console qui lance git.exe, lequel est une application
console, pousse Windows à en allouer une : une fenêtre noire apparaît, prend
le premier plan, puis disparaît. Avec une cinquantaine de commits dans
l'heure, le bureau devient inutilisable.

CREATE_NO_WINDOW coupe court : le processus enfant n'obtient aucune console, sa
sortie reste capturée normalement. L'indicateur n'existe que sous Windows,
ailleurs la valeur est nulle et ne change rien.
"""

from __future__ import annotations

import subprocess
import sys

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
