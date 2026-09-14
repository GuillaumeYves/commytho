"""Messages de commit et contenu ajouté au fichier suivi.

Le tirage est déterministe pour un créneau donné, comme le programme du jour.
Relancer le même tick deux fois produit donc le même message, ce qui évite les
doublons bizarres dans l'historique.

Vous pouvez remplacer entièrement cette liste avec un fichier texte, une ligne
par message, passé à l'option --messages de la commande up.
"""

from __future__ import annotations

import random
from datetime import date
from pathlib import Path

MESSAGES = [
    "Petite mise à jour du journal",
    "Note du jour",
    "Ajout d'une entrée",
    "Mise à jour des notes",
    "Journal : entrée du jour",
    "Complète le journal",
    "Relecture rapide",
    "Ajuste la mise en forme",
    "Range une ligne au bon endroit",
    "Continue le suivi",
    "Point d'étape",
    "Ajoute un repère de date",
    "Tient le journal à jour",
    "Nettoie une coquille",
    "Consigne l'avancement",
    "Reprend le fil",
    "Note de suivi",
    "Trace du passage du jour",
]


def load_pool(chemin: str | None) -> list[str]:
    """Charge une liste de messages personnalisée, sinon renvoie celle par défaut."""
    if not chemin:
        return MESSAGES
    fichier = Path(chemin).expanduser()
    lignes = [
        ligne.strip()
        for ligne in fichier.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.startswith("#")
    ]
    return lignes or MESSAGES


def pick(pool: list[str], jour: date, creneau: str) -> str:
    """Choisit un message pour un créneau précis, de façon reproductible."""
    rng = random.Random(f"message:{jour.isoformat()}:{creneau}")
    return rng.choice(pool)


def journal_line(jour: date, creneau: str, message: str) -> str:
    """Ligne ajoutée au fichier suivi du dépôt."""
    return f"- {jour.isoformat()} {creneau} : {message}\n"


def journal_header() -> str:
    """En-tête écrit à la création du fichier suivi."""
    return (
        "# Journal\n\nFichier tenu par commytho. Chaque ligne correspond à un créneau planifié.\n\n"
    )
