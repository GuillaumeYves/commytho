"""État courant : ce qui a déjà été fait aujourd'hui.

Ce fichier est la mémoire de commytho entre deux réveils. Il reste petit et
jetable : si on le supprime, le programme du jour est retiré à l'identique
grâce au tirage déterministe du planner, seule la liste des créneaux déjà
honorés est perdue.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from . import paths


@dataclass
class State:
    day: str = ""
    plan: list[str] = field(default_factory=list)
    done: list[str] = field(default_factory=list)
    last_run: str = ""
    total_commits: int = 0
    # Créneaux honorés les jours précédents, par date ISO. Sert à reprendre le
    # programme d'une journée où la machine est restée éteinte. La table est
    # élaguée à chaque changement de jour, elle ne grossit donc pas.
    history: dict[str, list[str]] = field(default_factory=dict)

    @property
    def remaining(self) -> int:
        return max(0, len(self.plan) - len(self.done))


def load() -> State:
    chemin = paths.state_file()
    if not chemin.exists():
        return State()
    try:
        raw = json.loads(chemin.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # Un état corrompu ne justifie pas de bloquer le tick : on repart à zéro.
        return State()
    champs = set(State.__dataclass_fields__)
    return State(**{k: v for k, v in raw.items() if k in champs})


def save(state: State) -> None:
    paths.ensure_dirs()
    chemin = paths.state_file()
    provisoire = chemin.with_suffix(".json.tmp")
    provisoire.write_text(
        json.dumps(asdict(state), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    provisoire.replace(chemin)


def roll_over(state: State, jour: date, plan: list[str], retention: int = 0) -> State:
    """Prépare l'état pour la journée en cours.

    Le compteur cumulé survit au changement de jour, la liste des créneaux
    honorés est remise à zéro. La journée qui se termine est versée à
    l'historique, où elle reste le nombre de jours demandé : sans cette trace,
    une reprise de session ne saurait pas distinguer une journée déjà honorée
    d'une journée entièrement manquée.
    """
    aujourdhui = jour.isoformat()
    if state.day == aujourdhui:
        state.plan = plan
        state.history = _elague(state.history, jour, retention)
        return state

    historique = dict(state.history)
    if state.day:
        historique[state.day] = list(state.done)
    return State(
        day=aujourdhui,
        plan=plan,
        done=[],
        total_commits=state.total_commits,
        history=_elague(historique, jour, retention),
    )


def _elague(history: dict[str, list[str]], jour: date, retention: int) -> dict[str, list[str]]:
    """Ne garde que les journées encore susceptibles d'être rattrapées."""
    if retention <= 0:
        return {}
    limite = jour - timedelta(days=retention)
    garde: dict[str, list[str]] = {}
    for cle, creneaux in history.items():
        try:
            quand = date.fromisoformat(cle)
        except ValueError:
            # Une clé illisible ne sert à rien et n'a pas à bloquer le réveil.
            continue
        if limite <= quand < jour:
            garde[cle] = creneaux
    return garde


def record(state: State, jour: date, creneaux: list[str]) -> None:
    """Note des créneaux honorés, le jour courant ou une journée rattrapée."""
    if jour.isoformat() == state.day:
        state.done.extend(creneaux)
        return
    deja = state.history.setdefault(jour.isoformat(), [])
    deja.extend(creneaux)
