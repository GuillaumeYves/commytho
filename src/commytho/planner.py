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
from datetime import date, timedelta

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

    Quand la plage est serrée, par exemple quarante commits dans une heure, les
    tranches deviennent plus courtes qu'une minute et plusieurs tirages tombent
    sur la même. Un créneau en double ne serait honoré qu'une fois : le
    programme rendrait moins de commits que le nombre tiré. Chaque doublon est
    donc décalé sur la minute libre la plus proche, sans sortir de la plage.
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
        minute = _minute_libre(rng.randint(borne_basse, borne_haute), creneaux, debut, fin)
        if minute is None:
            # La plage ne contient pas assez de minutes. On rend ce qu'on peut
            # plutôt que de boucler sur une place qui n'existe pas.
            break
        creneaux.add(minute)

    return [f"{m // 60:02d}:{m % 60:02d}" for m in sorted(creneaux)]


def _minute_libre(souhaitee: int, prises: set[int], debut: int, fin: int) -> int | None:
    """Première minute libre à partir de celle tirée, en avançant puis en reculant."""
    for minute in range(souhaitee, fin):
        if minute not in prises:
            return minute
    for minute in range(souhaitee - 1, debut - 1, -1):
        if minute not in prises:
            return minute
    return None


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


def backlog(
    schedule: Schedule,
    repo_full_name: str,
    history: dict[str, list[str]],
    aujourdhui: date,
    depuis: date | None = None,
) -> list[tuple[date, str]]:
    """Créneaux des journées passées restés sans commit, du plus ancien au plus récent.

    Une machine éteinte plusieurs jours perd tout son programme : le jour
    courant seul ne suffit pas à le rattraper. On remonte donc jusqu'à
    catch_up_days journées en arrière, en s'appuyant sur l'historique des
    créneaux honorés, et sur le tirage déterministe pour retrouver le programme
    d'un jour dont il ne reste aucune trace.

    Le paramètre depuis borne la remontée à la date de pose de la tâche : une
    installation toute neuve ne doit pas inventer une semaine d'activité.
    """
    jours = schedule.catch_up_days
    if jours <= 0:
        return []

    en_retard: list[tuple[date, str]] = []
    for recul in range(jours, 0, -1):
        jour = aujourdhui - timedelta(days=recul)
        if depuis is not None and jour < depuis:
            continue
        programme = plan_for_day(schedule, jour, repo_full_name)
        if not programme:
            continue
        faits = set(history.get(jour.isoformat(), []))
        restant = schedule.cap_per_day - len(faits)
        if restant <= 0:
            continue
        manques = [creneau for creneau in programme if creneau not in faits]
        # Le plafond du jour prime : on garde les créneaux les plus tardifs,
        # comme le fait déjà le rattrapage du jour courant.
        en_retard.extend((jour, creneau) for creneau in manques[-restant:])
    return en_retard
