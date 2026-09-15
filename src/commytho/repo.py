"""Opérations git sur la copie locale du dépôt cible.

commytho ne touche pas à vos dépôts de travail. Il garde sa propre copie dans
son dossier de données et ne travaille que là.

Le jeton n'apparaît jamais dans une ligne de commande ni dans .git/config. Il
est passé à git par un assistant d'identification éphémère qui lit une variable
d'environnement, ce qui le tient hors de la liste des processus.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath

from . import messages, paths
from .config import Config
from .console import NO_WINDOW

TOKEN_ENV = "COMMYTHO_GIT_TOKEN"

# Assistant d'identification en une ligne. git le confie à sh, y compris sous
# Windows où Git for Windows embarque son propre sh.
CREDENTIAL_HELPER = '!f() { echo username=x-access-token; echo "password=$' + TOKEN_ENV + '"; }; f'


class GitError(Exception):
    """Une commande git a échoué. Le message contient sa sortie."""


def run_git(args: list[str], cwd: Path | None = None, token: str | None = None) -> str:
    """Lance git et renvoie sa sortie standard.

    Quand un jeton est fourni, l'assistant d'identification est branché pour
    cette commande uniquement.
    """
    commande = ["git"]
    if token:
        commande += ["-c", f"credential.helper={CREDENTIAL_HELPER}"]
    commande += args

    env = os.environ.copy()
    if token:
        env[TOKEN_ENV] = token
    # Un prompt interactif bloquerait une tâche planifiée sans que rien ne
    # le signale. On préfère un échec net.
    env["GIT_TERMINAL_PROMPT"] = "0"

    resultat = subprocess.run(  # noqa: S603 - arguments construits par nos soins
        commande,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        # git est une application console : lancé depuis pythonw, qui n'a pas de
        # console, il en ferait apparaître une à chaque appel.
        creationflags=NO_WINDOW,
    )
    if resultat.returncode != 0:
        sortie = (resultat.stderr or resultat.stdout or "").strip()
        raise GitError(f"git {' '.join(args)} a échoué : {sortie}")
    return resultat.stdout.strip()


def git_available() -> bool:
    try:
        run_git(["--version"])
        return True
    except (GitError, FileNotFoundError):
        return False


def ensure_checkout(config: Config, token: str) -> Path:
    """Garantit une copie locale à jour du dépôt, et la renvoie.

    Premier appel : clonage. Appels suivants : on se recale sur la branche
    distante. Le contenu local n'a aucune valeur propre, donc un reset dur est
    la bonne réponse en cas de divergence.
    """
    destination = paths.checkout_dir()
    paths.ensure_dirs()

    if not (destination / ".git").exists():
        _premier_clonage(config, token, destination)
    else:
        run_git(["remote", "set-url", "origin", config.repo.https_url], cwd=destination)
        _resynchronise(config, token, destination)

    run_git(["config", "user.name", config.author.name], cwd=destination)
    run_git(["config", "user.email", config.author.email], cwd=destination)
    return destination


def _premier_clonage(config: Config, token: str, destination: Path) -> None:
    """Clone le dépôt, ou prépare un dépôt local si le distant est vide."""
    if destination.exists():
        # Dossier présent mais sans dépôt git : on ne devine pas, on refuse.
        if any(destination.iterdir()):
            raise GitError(
                f"{destination} existe et n'est pas un dépôt git. Videz ce dossier, puis relancez."
            )
        destination.rmdir()

    try:
        run_git(
            [
                "clone",
                "--depth",
                "1",
                "--branch",
                config.repo.branch,
                config.repo.https_url,
                str(destination),
            ],
            token=token,
        )
        return
    except GitError as exc:
        # Un dépôt créé sans README n'a aucun commit, donc aucune branche à
        # cloner. Ce cas est banal, on part alors d'un dépôt local vide et le
        # premier push créera la branche.
        if not _semble_vide(str(exc)):
            raise
        if destination.exists():
            _supprime_arborescence(destination)

    destination.mkdir(parents=True, exist_ok=True)
    run_git(["init", "-b", config.repo.branch], cwd=destination)
    run_git(["remote", "add", "origin", config.repo.https_url], cwd=destination)


def _resynchronise(config: Config, token: str, destination: Path) -> None:
    """Recale la copie locale sur la branche distante, si elle existe."""
    try:
        run_git(
            ["fetch", "--depth", "1", "origin", config.repo.branch], cwd=destination, token=token
        )
    except GitError:
        # La branche distante n'existe pas encore. La copie locale fait foi
        # jusqu'au premier push, qui la créera.
        run_git(["checkout", "-B", config.repo.branch], cwd=destination)
        return

    run_git(["checkout", "-B", config.repo.branch, "FETCH_HEAD"], cwd=destination)
    run_git(["reset", "--hard", "FETCH_HEAD"], cwd=destination)


def _semble_vide(message: str) -> bool:
    """Reconnaît le message de git quand le dépôt distant n'a aucun commit."""
    repere = message.lower()
    return any(
        texte in repere
        for texte in (
            "remote branch",
            "not found in upstream",
            "you appear to have cloned an empty repository",
            "empty repository",
        )
    )


def _supprime_arborescence(chemin: Path) -> None:
    """Efface un clone raté.

    Sous Windows, git pose des fichiers en lecture seule dans .git, que
    shutil.rmtree refuse de supprimer sans un coup de pouce.
    """
    import shutil
    import stat

    def force(fonction, cible, _exc):  # noqa: ANN001 - signature imposée par shutil
        Path(cible).chmod(stat.S_IWRITE)
        fonction(cible)

    shutil.rmtree(chemin, onerror=force)


@dataclass
class Commit:
    """Un commit réellement posé, avec le créneau qu'il honore."""

    jour: date
    creneau: str
    message: str
    hash: str


def make_commit(config: Config, token: str, jour: date, creneau: str, message: str) -> str:
    """Commite un seul créneau. Raccourci sur make_commits."""
    return make_commits(config, token, [(jour, creneau, message)])[0].hash


def make_commits(config: Config, token: str, entrees: list[tuple[date, str, str]]) -> list[Commit]:
    """Met à jour la copie locale, commite les créneaux demandés, pousse une fois.

    Le push est fait une seule fois, à la fin : rattraper un week-end éteint ne
    doit pas ouvrir quarante connexions à GitHub.
    """
    if not entrees:
        return []
    checkout = ensure_checkout(config, token)
    faits = commit_entries(config, checkout, entrees)
    if faits:
        run_git(["push", "origin", f"HEAD:{config.repo.branch}"], cwd=checkout, token=token)
    return faits


def commit_entries(
    config: Config, checkout: Path, entrees: list[tuple[date, str, str]]
) -> list[Commit]:
    """Commite les créneaux demandés dans une copie déjà à jour, sans pousser.

    Chaque entrée porte sa propre date : un réveil peut donc solder à la fois
    les créneaux du jour et ceux des journées manquées, chaque commit gardant
    l'horodatage de son créneau d'origine plutôt que celui du réveil.

    Un créneau déjà présent dans le journal est ignoré. C'est ce qui permet à
    plusieurs commytho de viser le même dépôt, celui de la machine et celui
    d'une action GitHub par exemple, sans se marcher dessus : le journal versé
    dans le dépôt fait foi, et non un fichier d'état local que l'autre ne voit
    pas.
    """
    if not entrees:
        return []

    deja = journal_slots(checkout, config.target_file)
    journal = Journal(checkout, config.target_file, config.max_lines_per_file)

    faits: list[Commit] = []
    for jour, creneau, message in entrees:
        if creneau in deja.get(jour.isoformat(), set()):
            continue
        suivi = journal.append(messages.journal_line(jour, creneau, message))
        with _dates_git(_iso_local(jour, creneau)):
            run_git(["add", "--", suivi], cwd=checkout)
            run_git(["commit", "-m", message], cwd=checkout)
        empreinte = run_git(["rev-parse", "--short", "HEAD"], cwd=checkout)
        faits.append(Commit(jour=jour, creneau=creneau, message=message, hash=empreinte))
    return faits


# Une ligne de journal, telle que messages.journal_line l'écrit.
LIGNE_JOURNAL = re.compile(r"^- (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) : ")


def journal_slots(checkout: Path, base: str) -> dict[str, set[str]]:
    """Créneaux déjà consignés dans le journal, par date ISO.

    Le journal est la seule mémoire partagée entre les machines qui alimentent
    le dépôt. Le relire coûte moins cher que de faire confiance à un état local
    qui peut avoir disparu, ou n'avoir jamais existé sur un runner.
    """
    releve: dict[str, set[str]] = {}
    for index in range(1, _dernier_index(checkout, base) + 1):
        chemin = checkout / _nom_indexe(base, index)
        if not chemin.exists():
            continue
        with chemin.open("r", encoding="utf-8", errors="replace") as fichier:
            for ligne in fichier:
                trouve = LIGNE_JOURNAL.match(ligne)
                if trouve:
                    releve.setdefault(trouve.group(1), set()).add(trouve.group(2))
    return releve


class Journal:
    """Le fichier alimenté dans le dépôt, et sa rotation quand il devient long.

    Un journal qui grossit sans fin finit par peser dans chaque diff et devient
    pénible à ouvrir sur GitHub. Passé le seuil, commytho ouvre le suivant :
    journal.md, puis journal-2.md, puis journal-3.md.

    Le numéro en cours est déduit des fichiers présents dans le dépôt, sans
    rien stocker à côté. Perdre le fichier d'état, ou installer commytho sur
    une seconde machine, ne fait donc pas repartir la rotation en arrière.
    """

    def __init__(self, checkout: Path, base: str, max_lignes: int) -> None:
        self.checkout = checkout
        self.base = base
        self.max_lignes = max_lignes
        self.index = _dernier_index(checkout, base)
        self.chemin = checkout / _nom_indexe(base, self.index)
        self.lignes = _compte_lignes(self.chemin)

    def append(self, ligne: str) -> str:
        """Ajoute une ligne et renvoie le chemin du fichier touché, relatif au dépôt."""
        if self.max_lignes > 0 and self.lignes >= self.max_lignes:
            self.index += 1
            self.chemin = self.checkout / _nom_indexe(self.base, self.index)
            self.lignes = _compte_lignes(self.chemin)

        if not self.chemin.exists():
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            entete = messages.journal_header(self.index)
            self.chemin.write_text(entete, encoding="utf-8")
            self.lignes = entete.count("\n")

        with self.chemin.open("a", encoding="utf-8") as fichier:
            fichier.write(ligne)
        self.lignes += ligne.count("\n")
        return self.chemin.relative_to(self.checkout).as_posix()


def _nom_indexe(base: str, index: int) -> str:
    """journal.md pour le premier fichier, journal-2.md pour le deuxième, etc."""
    if index <= 1:
        return base
    chemin = PurePosixPath(base.replace("\\", "/"))
    return str(chemin.with_name(f"{chemin.stem}-{index}{chemin.suffix}"))


def _dernier_index(checkout: Path, base: str) -> int:
    """Numéro du dernier fichier de la série présent dans le dépôt."""
    index = 1
    while (checkout / _nom_indexe(base, index + 1)).exists():
        index += 1
    return index


def _compte_lignes(chemin: Path) -> int:
    if not chemin.exists():
        return 0
    with chemin.open("r", encoding="utf-8", errors="replace") as fichier:
        return sum(1 for _ in fichier)


def active_target(config: Config, checkout: Path | None = None) -> str:
    """Fichier actuellement alimenté, pour l'affichage de la commande status."""
    dossier = checkout or paths.checkout_dir()
    if not dossier.exists():
        return config.target_file
    journal = Journal(dossier, config.target_file, config.max_lines_per_file)
    if config.max_lines_per_file > 0 and journal.lignes >= config.max_lines_per_file:
        return _nom_indexe(config.target_file, journal.index + 1)
    return _nom_indexe(config.target_file, journal.index)


@contextmanager
def _dates_git(horodatage: str) -> Iterator[None]:
    """Impose la date d'auteur et de commit, puis rend l'environnement intact."""
    variables = {"GIT_AUTHOR_DATE": horodatage, "GIT_COMMITTER_DATE": horodatage}
    ancien = {cle: os.environ.get(cle) for cle in variables}
    os.environ.update(variables)
    try:
        yield
    finally:
        for cle, valeur in ancien.items():
            if valeur is None:
                os.environ.pop(cle, None)
            else:
                os.environ[cle] = valeur


def _iso_local(jour: date, creneau: str) -> str:
    """Horodatage git au fuseau local de la machine."""
    heures, _, minutes = creneau.partition(":")
    moment = datetime(jour.year, jour.month, jour.day, int(heures), int(minutes))
    decalage = moment.astimezone().strftime("%z")
    return moment.strftime("%Y-%m-%dT%H:%M:%S") + decalage
