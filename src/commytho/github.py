"""Le strict minimum de l'API GitHub, en urllib.

Trois besoins seulement : savoir qui est connecté, vérifier qu'un dépôt existe,
et en créer un. Pas de dépendance HTTP supplémentaire pour si peu.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from . import __version__

API = "https://api.github.com"
TIMEOUT = 20


class GitHubError(Exception):
    """Réponse d'erreur de l'API, déjà traduite en message lisible."""


def _request(method: str, chemin: str, token: str, body: dict[str, Any] | None = None) -> Any:
    donnees = json.dumps(body).encode("utf-8") if body is not None else None
    requete = urllib.request.Request(  # noqa: S310 - URL construite en dur sur api.github.com
        f"{API}{chemin}",
        data=donnees,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": f"Bearer {token}",
            "User-Agent": f"commytho/{__version__}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(requete, timeout=TIMEOUT) as reponse:  # noqa: S310
            brut = reponse.read()
            return json.loads(brut) if brut else {}
    except urllib.error.HTTPError as exc:
        raise GitHubError(_explique(exc)) from exc
    except urllib.error.URLError as exc:
        raise GitHubError(f"GitHub est injoignable : {exc.reason}") from exc


def _explique(exc: urllib.error.HTTPError) -> str:
    """Transforme un code HTTP en phrase actionnable."""
    try:
        detail = json.loads(exc.read()).get("message", "")
    except Exception:  # noqa: BLE001 - corps vide ou non JSON
        detail = ""

    if exc.code == 401:
        return (
            "Jeton refusé par GitHub. Il est peut-être expiré ou révoqué. Relancez : commytho login"
        )
    if exc.code == 403:
        return (
            "Accès refusé. Vérifiez les permissions du jeton, "
            f"ou attendez la fin de la limitation de débit. {detail}".strip()
        )
    if exc.code == 404:
        return (
            "Ressource introuvable. Si le dépôt est privé, le jeton doit lui "
            "donner explicitement accès."
        )
    if exc.code == 422:
        return f"GitHub a refusé la demande : {detail or 'données invalides'}"
    return f"Erreur GitHub {exc.code} : {detail or exc.reason}"


def current_user(token: str) -> dict[str, Any]:
    """Compte associé au jeton."""
    return _request("GET", "/user", token)


def noreply_email(user: dict[str, Any]) -> str:
    """Adresse de commit sûre, rattachée au compte.

    GitHub ne compte une contribution que si l'adresse de l'auteur appartient au
    compte. L'adresse noreply remplit toujours cette condition, sans exposer
    l'adresse personnelle dans un dépôt public.
    """
    return f"{user['id']}+{user['login']}@users.noreply.github.com"


def get_repo(token: str, owner: str, name: str) -> dict[str, Any] | None:
    """Renvoie le dépôt, ou None s'il n'existe pas ou reste invisible au jeton."""
    try:
        return _request("GET", f"/repos/{owner}/{name}", token)
    except GitHubError as exc:
        if "introuvable" in str(exc):
            return None
        raise


def create_repo(token: str, name: str, private: bool, description: str) -> dict[str, Any]:
    """Crée un dépôt sur le compte du jeton, avec un README de départ."""
    return _request(
        "POST",
        "/user/repos",
        token,
        {
            "name": name,
            "private": private,
            "description": description,
            "auto_init": True,
        },
    )
