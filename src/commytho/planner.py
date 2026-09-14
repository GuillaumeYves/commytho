"""Construction du programme de la journée.

Le principe : la tâche planifiée réveille commytho toutes les N minutes, mais
elle ne commite pas à chaque réveil. Chaque jour, on tire un programme, par
exemple 09:47, 13:12 et 17:29, et un réveil ne fait quelque chose que si un
créneau est arrivé à échéance.

Le tirage est déterministe pour un couple (dépôt, date). Deux réveils du même
jour obtiennent donc le même programme, même si le fichier d'état a disparu.
"""

from __future__ import annotations

import random
from datetime import date

from .config import Schedule


def day_seed(repo_full_name: str, jour: date) -> str:
    """Graine stable pour une journée donnée.

    Le nom du dépôt entre dans la graine pour que deux installations qui
    visent des dépôts différents ne tirent pas les mêmes horaires.
    """
    return f"commytho:{repo_full_name}:{jour.isoformat()}"


def commits_planned(schedule: Schedule, jour: date, repo_full_name: str) -> int:
    """Nombre de commits tirés pour cette journée, plafond compris."""
    if jour.weekday() not in schedule.days:
        return 0
    rng = random.Random(day_seed(repo_full_name, jour))
    mini = max(0, schedule.min_per_day)
    maxi = max(mini, schedule.max_per_day)
    return min(rng.randint(mini, maxi), schedule.cap_per_day)


def plan_for_day(schedule: Schedule, jour: date, repo_full_name: str) -> list[str]:
    """Renvoie les horaires du jour, triés, au format HH:MM.

    Les créneaux sont répartis en tranches égales dans la plage horaire, avec
    un tirage aléatoire à l'intérieur de chaque tranche. On évite ainsi les
    paquets de commits à la même minute, tout en gardant un rythme irrégulier.
    """
    nombre = commits_planned(schedule, jour, repo_full_name)
    if nombre == 0:
        return []

    debut = _minutes(schedule.window_start)
    fin = _minutes(schedule.window_end)
    duree = fin - debut
    if duree <= 0:
        return []

    rng = random.Random(day_seed(repo_full_name, jour) + ":horaires")
    largeur = duree / nombre
    creneaux: set[int] = set()
    for index in range(nombre):
        borne_basse = debut + int(index * largeur)
        borne_haute = debut + int((index + 1) * largeur) - 1
        if borne_haute < borne_basse:
            borne_haute = borne_basse
        creneaux.add(rng.randint(borne_basse, borne_haute))

    return [f"{m // 60:02d}:{m % 60:02d}" for m in sorted(creneaux)]


def due_slots(plan: list[str], done: list[str], maintenant: str) -> list[str]:
    """Créneaux déjà passés et pas encore honorés.

    Si la machine était éteinte, plusieurs créneaux peuvent être en retard.
    L'appelant décide s'il les rattrape tous ou seulement le dernier.
    """
    limite = _minutes(maintenant)
    deja = set(done)
    return [c for c in plan if c not in deja and _minutes(c) <= limite]


def _minutes(heure: str) -> int:
    h, _, m = heure.partition(":")
    return int(h) * 60 + int(m)
