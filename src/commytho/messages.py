"""Messages de commit et contenu ajouté au fichier suivi.

Le tirage est déterministe pour un créneau donné, comme le programme du jour.
Relancer le même tick deux fois produit donc le même message, ce qui évite les
doublons bizarres dans l'historique.

Vous pouvez remplacer entièrement cette liste avec un fichier texte, une ligne
par message, passé à l'option --messages de la commande up.

L'ordre et la longueur de la liste comptent : le tirage retient une position,
pas un texte. Ajouter un message au milieu décale tout ce qui suit et change
les messages que les prochains créneaux obtiendront.
"""

from __future__ import annotations

import random
from datetime import date
from pathlib import Path

MESSAGES = [
    "Petite mise à jour du journal.",
    "Note du jour.",
    "Ajout d'une entrée.",
    "Mise à jour des notes.",
    "Journal : entrée du jour.",
    "Complète le journal.",
    "Relecture rapide.",
    "Ajuste la mise en forme.",
    "Range une ligne au bon endroit.",
    "Continue le suivi.",
    "Point d'étape.",
    "Ajoute un repère de date.",
    "Tient le journal à jour.",
    "Nettoie une coquille.",
    "Consigne l'avancement.",
    "Reprend le fil.",
    "Note de suivi.",
    "Trace du passage du jour.",
    # Quelques messages plus légers. Le journal n'a pas à être solennel, et un
    # historique entièrement composé de phrases neutres finit par se voir
    # autant qu'un historique trop régulier.
    "Commit avant d'oublier.",
    "Le café a fini par faire effet.",
    "Une ligne pour la route.",
    "Je note, donc je suis.",
    "Le futur moi comprendra.",
    "Trois mots, et au lit.",
    "Rien de cassé, promis.",
    "Déplace une virgule, change le monde.",
    "Ça tenait dans la marge.",
    "Petit commit entre amis.",
    "On verra ça demain.",
    "Encore une idée attrapée au vol.",
    "Le journal ne s'écrit pas tout seul.",
    "Un jour de plus, une ligne de plus.",
    "Écrit d'une main, café dans l'autre.",
    "Ceci méritait bien une ligne.",
    "Rangement de fin de journée.",
    "Noté avant que ça s'envole.",
    "Deux minutes bien employées.",
    "La suite au prochain épisode...",
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


def journal_header(index: int = 1) -> str:
    """En-tête écrit à la création d'un fichier suivi.

    L'index apparaît dans le titre dès le deuxième fichier, pour qu'un journal
    ouvert seul indique tout de suite où il se situe dans la série.
    """
    titre = "# Journal" if index <= 1 else f"# Journal, suite {index}"
    corps = "Fichier tenu par commytho. Chaque ligne correspond à un créneau planifié."
    return f"{titre}\n\n{corps}\n\n"
