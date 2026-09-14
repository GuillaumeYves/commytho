"""Pose et retrait de la tâche planifiée, selon le système.

Un planificateur expose quatre choses : un nom, install, uninstall, status.
Le choix se fait au moment de l'appel, jamais à l'import, pour que les tests
puissent instancier n'importe quelle implémentation sur n'importe quelle machine.
"""

from __future__ import annotations

import sys

from .base import Scheduler, tick_command


def get_scheduler() -> Scheduler:
    """Renvoie le planificateur adapté à la machine courante."""
    if sys.platform == "win32":
        from .windows import WindowsScheduler

        return WindowsScheduler()
    if sys.platform == "darwin":
        from .launchd import LaunchdScheduler

        return LaunchdScheduler()

    from .systemd import pick_unix_scheduler

    return pick_unix_scheduler()


__all__ = ["Scheduler", "get_scheduler", "tick_command"]
