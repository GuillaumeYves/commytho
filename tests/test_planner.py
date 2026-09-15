"""Tests du tirage du programme quotidien."""

from datetime import date, timedelta

from commytho.config import Schedule
from commytho.planner import backlog, commits_planned, due_slots, plan_for_day

DEPOT = "alice/journal"
UN_LUNDI = date(2026, 9, 14)
UN_SAMEDI = date(2026, 9, 19)


def test_le_programme_est_stable_pour_une_meme_journee():
    planning = Schedule()
    premier = plan_for_day(planning, UN_LUNDI, DEPOT)
    second = plan_for_day(planning, UN_LUNDI, DEPOT)
    assert premier == second


def test_deux_depots_ont_des_programmes_differents():
    planning = Schedule(min_per_day=3, max_per_day=3)
    a = plan_for_day(planning, UN_LUNDI, "alice/journal")
    b = plan_for_day(planning, UN_LUNDI, "bob/journal")
    assert a != b


def test_rien_un_jour_non_retenu():
    planning = Schedule(days=[0, 1, 2, 3, 4])
    assert plan_for_day(planning, UN_SAMEDI, DEPOT) == []


def test_le_plafond_ecrase_le_maximum_demande():
    planning = Schedule(min_per_day=50, max_per_day=50, cap_per_day=20)
    assert commits_planned(planning, UN_LUNDI, DEPOT) == 20


def test_les_creneaux_restent_dans_la_plage_horaire():
    planning = Schedule(min_per_day=5, max_per_day=5, window_start="10:00", window_end="12:00")
    for creneau in plan_for_day(planning, UN_LUNDI, DEPOT):
        heures, _, minutes = creneau.partition(":")
        total = int(heures) * 60 + int(minutes)
        assert 600 <= total < 720


def test_les_creneaux_sont_tries_et_distincts():
    planning = Schedule(min_per_day=8, max_per_day=8)
    creneaux = plan_for_day(planning, UN_LUNDI, DEPOT)
    assert creneaux == sorted(creneaux)
    assert len(creneaux) == len(set(creneaux))


def test_une_plage_horaire_vide_ne_produit_rien():
    planning = Schedule(window_start="09:00", window_end="09:00")
    assert plan_for_day(planning, UN_LUNDI, DEPOT) == []


def test_seuls_les_creneaux_passes_sont_dus():
    programme = ["09:00", "12:00", "17:00"]
    assert due_slots(programme, [], "13:00") == ["09:00", "12:00"]


def test_un_creneau_deja_honore_nest_plus_du():
    programme = ["09:00", "12:00"]
    assert due_slots(programme, ["09:00"], "13:00") == ["12:00"]


def test_aucun_creneau_du_avant_la_plage():
    assert due_slots(["14:00"], [], "08:00") == []


def test_une_plage_serree_rend_bien_tous_les_creneaux():
    # Quarante commits dans une heure : les tranches font moins d'une minute,
    # et sans décalage des doublons le programme rendrait moitié moins.
    planning = Schedule(
        min_per_day=40,
        max_per_day=40,
        cap_per_day=40,
        window_start="07:00",
        window_end="08:00",
    )
    creneaux = plan_for_day(planning, UN_LUNDI, DEPOT)
    assert len(creneaux) == 40
    assert len(set(creneaux)) == 40
    assert creneaux[0] >= "07:00" and creneaux[-1] < "08:00"


def test_une_plage_trop_courte_rend_ce_quelle_peut():
    planning = Schedule(
        min_per_day=30,
        max_per_day=30,
        cap_per_day=30,
        window_start="09:00",
        window_end="09:10",
    )
    creneaux = plan_for_day(planning, UN_LUNDI, DEPOT)
    # Dix minutes ne contiennent pas trente créneaux distincts, et commytho ne
    # doit pas boucler à chercher une place qui n'existe pas.
    assert len(creneaux) == 10


def test_aucune_reprise_quand_elle_est_desactivee():
    planning = Schedule(days=list(range(7)), catch_up_days=0)
    assert backlog(planning, DEPOT, {}, UN_LUNDI) == []


def test_la_reprise_couvre_les_journees_sans_trace():
    planning = Schedule(days=list(range(7)), min_per_day=2, max_per_day=2, catch_up_days=3)
    manques = backlog(planning, DEPOT, {}, UN_LUNDI)
    journees = sorted({jour for jour, _ in manques})
    assert journees == [UN_LUNDI - timedelta(days=n) for n in (3, 2, 1)]
    # Le jour courant n'entre pas dans la reprise : il a son propre chemin.
    assert UN_LUNDI not in journees


def test_la_reprise_ignore_les_creneaux_deja_honores():
    planning = Schedule(days=list(range(7)), min_per_day=3, max_per_day=3, catch_up_days=1)
    veille = UN_LUNDI - timedelta(days=1)
    complet = plan_for_day(planning, veille, DEPOT)
    historique = {veille.isoformat(): complet[:1]}
    manques = [creneau for _, creneau in backlog(planning, DEPOT, historique, UN_LUNDI)]
    assert manques == complet[1:]


def test_la_reprise_ne_remonte_pas_avant_la_pose():
    planning = Schedule(days=list(range(7)), min_per_day=2, max_per_day=2, catch_up_days=5)
    pose = UN_LUNDI - timedelta(days=2)
    journees = {jour for jour, _ in backlog(planning, DEPOT, {}, UN_LUNDI, depuis=pose)}
    assert min(journees) == pose


def test_la_reprise_respecte_le_plafond_de_chaque_journee():
    planning = Schedule(
        days=list(range(7)), min_per_day=5, max_per_day=5, cap_per_day=5, catch_up_days=1
    )
    veille = UN_LUNDI - timedelta(days=1)
    complet = plan_for_day(planning, veille, DEPOT)
    # Trois créneaux déjà faits, le plafond n'en autorise plus que deux.
    historique = {veille.isoformat(): complet[:3]}
    manques = [creneau for _, creneau in backlog(planning, DEPOT, historique, UN_LUNDI)]
    assert manques == complet[-2:]
