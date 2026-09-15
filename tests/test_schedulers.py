"""Tests des parties des planificateurs qui ne touchent pas au système.

Poser une vraie tâche planifiée dans un test laisserait des traces sur la
machine qui lance la suite. On se limite donc ici à ce qui est vérifiable sans
effet de bord, et la CI couvre le reste en installant le paquet pour de vrai.
"""

import sys

import pytest

from commytho import repo
from commytho.schedulers.base import python_executable, tick_command


def test_la_commande_de_reveil_est_absolue():
    executable, *arguments = tick_command()
    # La tâche planifiée hérite rarement du PATH de votre session. Un chemin
    # absolu est la seule garantie que le bon interpréteur sera appelé.
    assert executable == python_executable()
    assert arguments == ["-m", "commytho", "run"]
    assert len(executable) > len("python")


@pytest.mark.skipif(sys.platform != "win32", reason="spécifique à Windows")
def test_la_ligne_schtasks_protege_les_espaces():
    from commytho.schedulers.windows import _ligne_de_commande

    ligne = _ligne_de_commande()
    assert ligne.startswith('"')
    assert ligne.endswith("-m commytho run")


def test_planification_cron_sous_lheure():
    assert _planning_cron(30) == "*/30 * * * *"


def test_planification_cron_au_dela_de_lheure():
    assert _planning_cron(120) == "0 */2 * * *"


def _planning_cron(minutes: int) -> str:
    """Reprend la règle de CronScheduler.install sans rien écrire sur la machine."""
    if minutes >= 60:
        return f"0 */{max(1, minutes // 60)} * * *"
    return f"*/{max(1, minutes)} * * * *"


@pytest.mark.parametrize(
    "message",
    [
        "git clone a échoué : fatal: Remote branch main not found in upstream origin",
        "warning: You appear to have cloned an empty repository",
    ],
)
def test_un_depot_sans_commit_est_reconnu(message):
    assert repo._semble_vide(message)


def test_une_vraie_erreur_nest_pas_prise_pour_un_depot_vide():
    assert not repo._semble_vide("fatal: Authentication failed for https://github.com/a/b.git")


def test_horodatage_git_au_fuseau_local():
    from datetime import date

    horodatage = repo._iso_local(date(2026, 9, 14), "09:47")
    assert horodatage.startswith("2026-09-14T09:47:00")
    # Un fuseau est toujours présent, sinon git prendrait l'heure du réveil.
    assert horodatage[-5] in {"+", "-"}


@pytest.mark.skipif(sys.platform != "win32", reason="spécifique à Windows")
def test_le_xml_de_la_tache_desarme_la_batterie():
    from commytho.schedulers.windows import _definition_xml

    definition = _definition_xml(30)
    # Sans ces deux lignes, un portable débranché ne commite pas une seule
    # fois, et Windows n'en dit rien nulle part.
    assert "<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>" in definition
    assert "<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>" in definition
    assert "<Interval>PT30M</Interval>" in definition


@pytest.mark.skipif(sys.platform != "win32", reason="spécifique à Windows")
def test_le_xml_de_la_tache_pointe_le_bon_interpreteur():
    from commytho.schedulers.windows import _definition_xml

    definition = _definition_xml(30)
    executable, *arguments = tick_command()
    # Le XML sépare l'exécutable de ses arguments, là où /TR attend une seule
    # chaîne : pas de guillemets à ajouter autour du chemin.
    assert f"<Command>{executable}</Command>" in definition
    assert f"<Arguments>{' '.join(arguments)}</Arguments>" in definition


@pytest.mark.skipif(sys.platform != "win32", reason="spécifique à Windows")
def test_le_xml_de_la_tache_masque_la_fenetre():
    from commytho.schedulers.windows import _definition_xml

    definition = _definition_xml(30)
    # Une salve de commits ne doit pas faire clignoter la moindre fenêtre au
    # premier plan, ni voler le focus de ce que l'on est en train de faire.
    assert "<Hidden>true</Hidden>" in definition


def test_les_processus_enfants_nouvrent_pas_de_console():
    import subprocess

    from commytho.console import NO_WINDOW

    if sys.platform == "win32":
        assert NO_WINDOW == subprocess.CREATE_NO_WINDOW
    else:
        # Ailleurs l'indicateur n'existe pas, et subprocess refuse toute valeur
        # non nulle : la valeur neutre est la seule acceptable.
        assert NO_WINDOW == 0
