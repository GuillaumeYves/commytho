"""Tests du tirage du programme quotidien."""

from datetime import date

from commytho.config import Schedule
from commytho.planner import commits_planned, due_slots, plan_for_day

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
