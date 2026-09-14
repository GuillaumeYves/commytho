"""Opérations git sur la copie locale du dépôt cible.

commytho ne touche pas à vos dépôts de travail. Il garde sa propre copie dans
son dossier de données et ne travaille que là.

Le jeton n'apparaît jamais dans une ligne de commande ni dans .git/config. Il
est passé à git par un assistant d'identification éphémère qui lit une variable
d'environnement, ce qui le tient hors de la liste des processus.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from . import messages, paths
from .config import Config

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


def make_commit(config: Config, token: str, jour: date, creneau: str, message: str) -> str:
    """Commite un seul créneau. Raccourci sur make_commits."""
    return make_commits(config, token, jour, [(creneau, message)])[0]


def make_commits(
    config: Config, token: str, jour: date, creneaux: list[tuple[str, str]]
) -> list[str]:
    """Commite une série de créneaux, pousse une fois, renvoie les hashs courts.

    La date de chaque commit est celle de son créneau, pas celle du réveil. Un
    rattrapage après une machine éteinte reste donc cohérent avec le programme
    du jour, même si les quarante commits partent dans la même seconde.

    Le push est fait une seule fois, à la fin : rattraper un week-end éteint ne
    doit pas ouvrir quarante connexions à GitHub.
    """
    if not creneaux:
        return []

    checkout = ensure_checkout(config, token)
    cible = checkout / config.target_file
    cible.parent.mkdir(parents=True, exist_ok=True)

    if not cible.exists():
        cible.write_text(messages.journal_header(), encoding="utf-8")

    empreintes: list[str] = []
    for creneau, message in creneaux:
        with cible.open("a", encoding="utf-8") as fichier:
            fichier.write(messages.journal_line(jour, creneau, message))
        with _dates_git(_iso_local(jour, creneau)):
            run_git(["add", "--", config.target_file], cwd=checkout)
            run_git(["commit", "-m", message], cwd=checkout)
        empreintes.append(run_git(["rev-parse", "--short", "HEAD"], cwd=checkout))

    run_git(["push", "origin", f"HEAD:{config.repo.branch}"], cwd=checkout, token=token)
    return empreintes


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
