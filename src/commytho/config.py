"""Lecture et écriture de config.json, plus les valeurs par défaut.

La configuration est volontairement plate et lisible : on veut pouvoir l'ouvrir
dans un éditeur, comprendre ce qui est planifié, et corriger à la main si besoin.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from . import paths

CONFIG_VERSION = 1

# Plafond conseillé. Au-delà, le rythme cesse d'être crédible et commytho
# affiche un avertissement. Ce n'est pas un blocage : c'est votre dépôt.
RECOMMENDED_MAX_PER_DAY = 20

DAY_NAMES = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]


class ConfigError(Exception):
    """Configuration absente, illisible, ou incohérente."""


@dataclass
class Schedule:
    """Le rythme demandé. Les heures sont locales à la machine."""

    days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])
    min_per_day: int = 1
    max_per_day: int = 3
    cap_per_day: int = RECOMMENDED_MAX_PER_DAY
    window_start: str = "09:00"
    window_end: str = "19:00"
    tick_minutes: int = 30

    def describe(self) -> str:
        """Résumé sur une ligne, utilisé par la commande status."""
        jours = ", ".join(DAY_NAMES[d] for d in sorted(self.days)) or "aucun"
        return (
            f"{self.min_per_day} à {self.max_per_day} commits par jour, "
            f"entre {self.window_start} et {self.window_end}, "
            f"les jours suivants : {jours} (plafond {self.cap_per_day})"
        )


@dataclass
class Repo:
    """Le dépôt cible. commytho ne touche jamais à autre chose."""

    owner: str = ""
    name: str = ""
    branch: str = "main"
    private: bool = False

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def https_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.name}.git"


@dataclass
class Author:
    """Identité git utilisée pour les commits.

    L'adresse doit être rattachée au compte GitHub, sinon les commits
    n'apparaissent pas dans le graphe de contributions.
    """

    name: str = ""
    email: str = ""


@dataclass
class Installed:
    """Trace de la tâche planifiée réellement posée sur la machine."""

    kind: str = ""
    identifier: str = ""
    installed_at: str = ""


@dataclass
class Config:
    version: int = CONFIG_VERSION
    repo: Repo = field(default_factory=Repo)
    author: Author = field(default_factory=Author)
    schedule: Schedule = field(default_factory=Schedule)
    target_file: str = "journal.md"
    installed: Installed = field(default_factory=Installed)

    @property
    def is_linked(self) -> bool:
        return bool(self.repo.owner and self.repo.name)


def _from_dict(raw: dict[str, Any]) -> Config:
    """Reconstruit un Config en ignorant les clés inconnues.

    Une clé en trop, par exemple une config écrite par une version plus récente,
    ne doit pas faire planter la commande. On préfère perdre l'option que bloquer
    l'outil.
    """

    def keep(cls: type, data: dict[str, Any]) -> dict[str, Any]:
        champs = set(cls.__dataclass_fields__)
        return {k: v for k, v in (data or {}).items() if k in champs}

    return Config(
        version=raw.get("version", CONFIG_VERSION),
        repo=Repo(**keep(Repo, raw.get("repo", {}))),
        author=Author(**keep(Author, raw.get("author", {}))),
        schedule=Schedule(**keep(Schedule, raw.get("schedule", {}))),
        target_file=raw.get("target_file", "journal.md"),
        installed=Installed(**keep(Installed, raw.get("installed", {}))),
    )


def load() -> Config:
    """Charge la configuration, ou renvoie les valeurs par défaut si le fichier manque."""
    chemin = paths.config_file()
    if not chemin.exists():
        return Config()
    try:
        raw = json.loads(chemin.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"Configuration illisible ({chemin}). Corrigez le fichier ou supprimez-le : {exc}"
        ) from exc
    return _from_dict(raw)


def save(config: Config) -> None:
    """Écrit la configuration de façon atomique.

    Un tick peut tourner pendant qu'on édite la config. On évite de laisser
    un fichier à moitié écrit derrière nous.
    """
    paths.ensure_dirs()
    chemin = paths.config_file()
    provisoire = chemin.with_suffix(".json.tmp")
    provisoire.write_text(
        json.dumps(asdict(config), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    provisoire.replace(chemin)


def parse_days(expression: str) -> list[int]:
    """Traduit une expression de jours en indices, 0 valant lundi.

    Accepte "lun-ven", "sam,dim", "tous", "semaine", "weekend", ainsi que les
    noms anglais courants pour dépanner.
    """
    alias = {
        "lun": 0,
        "mar": 1,
        "mer": 2,
        "jeu": 3,
        "ven": 4,
        "sam": 5,
        "dim": 6,
        "mon": 0,
        "tue": 1,
        "wed": 2,
        "thu": 3,
        "fri": 4,
        "sat": 5,
        "sun": 6,
    }
    texte = expression.strip().lower()
    if texte in {"tous", "all", "quotidien"}:
        return list(range(7))
    if texte in {"semaine", "weekdays"}:
        return [0, 1, 2, 3, 4]
    if texte in {"weekend", "we"}:
        return [5, 6]

    jours: set[int] = set()
    for brut in texte.split(","):
        morceau = brut.strip()
        if not morceau:
            continue
        if "-" in morceau:
            debut, _, fin = morceau.partition("-")
            if debut not in alias or fin not in alias:
                raise ConfigError(f"Jour inconnu dans la plage : {morceau}")
            i, j = alias[debut], alias[fin]
            # Une plage peut enjamber le dimanche, par exemple "ven-lun".
            while True:
                jours.add(i)
                if i == j:
                    break
                i = (i + 1) % 7
        else:
            if morceau not in alias:
                raise ConfigError(f"Jour inconnu : {morceau}")
            jours.add(alias[morceau])
    if not jours:
        raise ConfigError("Aucun jour retenu.")
    return sorted(jours)


def parse_range(expression: str) -> tuple[int, int]:
    """Lit "2" ou "1-4" et renvoie un intervalle (minimum, maximum)."""
    texte = expression.strip()
    try:
        if "-" in texte:
            gauche, _, droite = texte.partition("-")
            mini, maxi = int(gauche), int(droite)
        else:
            mini = maxi = int(texte)
    except ValueError as exc:
        raise ConfigError(f"Fréquence illisible : {expression}") from exc
    if mini < 0 or maxi < mini:
        raise ConfigError(f"Fréquence incohérente : {expression}")
    return mini, maxi


def parse_window(expression: str) -> tuple[str, str]:
    """Lit "09:00-19:00" et renvoie les deux bornes normalisées."""
    gauche, sep, droite = expression.partition("-")
    if not sep:
        raise ConfigError("La plage horaire doit ressembler à 09:00-19:00")
    debut, fin = _normalise_heure(gauche), _normalise_heure(droite)
    if minutes_of(fin) <= minutes_of(debut):
        raise ConfigError("La fin de la plage horaire doit suivre son début.")
    return debut, fin


def _normalise_heure(valeur: str) -> str:
    texte = valeur.strip()
    try:
        heures, _, minutes = texte.partition(":")
        h, m = int(heures), int(minutes or 0)
    except ValueError as exc:
        raise ConfigError(f"Heure illisible : {valeur}") from exc
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ConfigError(f"Heure hors limites : {valeur}")
    return f"{h:02d}:{m:02d}"


def minutes_of(heure: str) -> int:
    """Convertit 14:30 en nombre de minutes depuis minuit."""
    h, _, m = heure.partition(":")
    return int(h) * 60 + int(m)
