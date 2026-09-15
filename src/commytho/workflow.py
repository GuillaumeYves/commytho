"""Génération du workflow GitHub qui tient le journal quand la machine est éteinte.

Le principe est le même que sur la machine : une seule visite par jour, après
la fermeture de la plage horaire, qui pose d'un coup tous les commits du
programme avec l'horodatage de leur créneau. Un réveil en retard ne se voit
donc pas, ce qui tombe bien : GitHub décale volontiers les tâches planifiées de
plusieurs dizaines de minutes, et en saute parfois.

Le créneau cron est calculé avec trois heures de marge après la fin de la plage,
et interprété par GitHub en UTC. Plutôt que de deviner le décalage de la machine
et de le voir changer deux fois par an, on laisse la marge absorber l'écart : la
reprise des journées passées rattrape de toute façon ce qu'une visite mal tombée
aurait laissé.

Le workflow ne demande aucun secret. actions/checkout laisse ses identifiants
dans la copie, et la permission contents: write suffit à pousser. Les commits
gardent l'adresse de l'auteur, qui est ce que GitHub regarde pour le graphe des
contributions.

La visite porte une date de départ. Sans elle, la toute première remonterait
sept jours en arrière et inventerait une semaine d'activité, le journal du
dépôt étant sa seule mémoire.
"""

from __future__ import annotations

from datetime import date

from .config import DAY_NAMES, Config, minutes_of

WORKFLOW_PATH = ".github/workflows/journal.yml"

SOURCE_PAR_DEFAUT = "git+https://github.com/GuillaumeYves/commytho@main"


def cron_apres(window_end: str) -> str:
    """Créneau cron quotidien, trois heures après la fermeture de la plage."""
    heure = (minutes_of(window_end) // 60 + 3) % 24
    return f"0 {heure} * * *"


def describe_days(config: Config) -> str:
    """Rend l'expression de jours attendue par les options de la ligne de commande."""
    jours = sorted(config.schedule.days)
    if jours == list(range(7)):
        return "tous"
    if jours == [0, 1, 2, 3, 4]:
        return "lun-ven"
    if jours == [5, 6]:
        return "weekend"
    return ",".join(DAY_NAMES[d] for d in jours)


def render(
    config: Config,
    source: str = SOURCE_PAR_DEFAUT,
    timezone: str = "",
    since: date | None = None,
) -> str:
    """Compose le fichier de workflow à déposer dans le dépôt cible."""
    planning = config.schedule
    auteur = f"{config.author.name} <{config.author.email}>"
    # Le bloc env ne sort que s'il a quelque chose à contenir : une clé env
    # sans valeur ferait refuser le fichier par GitHub.
    env = f"        env:\n          TZ: {timezone}\n" if timezone else ""
    note_tz = (
        ""
        if timezone
        else (
            "# Aucun fuseau n'a été précisé : le runner travaille en UTC et les\n"
            "# commits porteront ce décalage. commytho github --tz Europe/Paris\n"
            "# les remet à l'heure de chez vous.\n"
        )
    )
    return f"""name: journal

# Fichier tenu par commytho, ne le modifiez pas à la main : il est réécrit à
# chaque commytho github. Pour changer de rythme, passez par commytho up sur
# votre machine, puis reposez le workflow.
#
# Une seule visite par jour, après la fermeture de la plage horaire. Elle pose
# d'un coup les commits du programme du jour, et reprend au passage les
# journées restées vides. Chaque commit garde la date et l'heure de son
# créneau, pas celles de la visite : que GitHub arrive en retard ne se voit pas.
{note_tz}
on:
  schedule:
    - cron: "{cron_apres(planning.window_end)}"
  workflow_dispatch:

permissions:
  contents: write

# Deux visites qui se chevauchent pousseraient les mêmes créneaux deux fois.
concurrency:
  group: journal
  cancel-in-progress: false

jobs:
  tenir:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Installe commytho
        run: python -m pip install --quiet "commytho @ {source}"
      - name: Tient le journal
{env}        run: >
          commytho ci --verbose
          --repo {config.repo.full_name}
          --branch {config.repo.branch}
          --author "{auteur}"
          --per-day {planning.min_per_day}-{planning.max_per_day}
          --days {describe_days(config)}
          --window {planning.window_start}-{planning.window_end}
          --max {planning.cap_per_day}
          --file {config.target_file}
          --max-lines {config.max_lines_per_file}
          --jours {max(planning.catch_up_days, 7)}
          --depuis {(since or date.today()).isoformat()}
"""
