"""État courant : ce qui a déjà été fait aujourd'hui.

Ce fichier est la mémoire de commytho entre deux réveils. Il reste petit et
jetable : si on le supprime, le programme du jour est retiré à l'identique
grâce au tirage déterministe du planner, seule la liste des créneaux déjà
honorés est perdue.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date

from . import paths


@dataclass
class State:
    day: str = ""
    plan: list[str] = field(default_factory=list)
    done: list[str] = field(default_factory=list)
    last_run: str = ""
    total_commits: int = 0

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


def roll_over(state: State, jour: date, plan: list[str]) -> State:
    """Prépare l'état pour la journée en cours.

    Le compteur cumulé survit au changement de jour, la liste des créneaux
    honorés est remise à zéro.
    """
    aujourdhui = jour.isoformat()
    if state.day == aujourdhui:
        state.plan = plan
        return state
    return State(day=aujourdhui, plan=plan, done=[], total_commits=state.total_commits)
