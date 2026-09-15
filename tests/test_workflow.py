"""Tests du workflow GitHub et de la visite qu'il déclenche.

Rien ici ne parle à GitHub : on vérifie le fichier produit, et le fait que le
journal versé dans le dépôt suffise à savoir ce qui reste à poser.
"""

from datetime import date

import pytest

from commytho import config as conf
from commytho import repo, workflow


@pytest.fixture
def configuration():
    reglage = conf.Config()
    reglage.repo = conf.Repo(owner="alice", name="journal", branch="main")
    reglage.author = conf.Author(name="Alice", email="1+alice@users.noreply.github.com")
    reglage.schedule.days = list(range(7))
    reglage.schedule.min_per_day = 30
    reglage.schedule.max_per_day = 50
    reglage.schedule.cap_per_day = 50
    reglage.schedule.window_start = "07:00"
    reglage.schedule.window_end = "08:00"
    return reglage


def test_la_visite_tombe_apres_la_fermeture_de_la_plage():
    # Trois heures de marge : GitHub interprète le cron en UTC, et décale
    # volontiers ses tâches planifiées de plusieurs dizaines de minutes.
    assert workflow.cron_apres("08:00") == "0 11 * * *"
    assert workflow.cron_apres("19:00") == "0 22 * * *"


def test_une_plage_qui_finit_tard_repasse_par_minuit():
    assert workflow.cron_apres("23:00") == "0 2 * * *"


def test_le_workflow_reprend_le_rythme_configure(configuration):
    rendu = workflow.render(configuration)
    assert "--per-day 30-50" in rendu
    assert "--window 07:00-08:00" in rendu
    assert "--days tous" in rendu
    assert "--repo alice/journal" in rendu
    assert '--author "Alice <1+alice@users.noreply.github.com>"' in rendu


def test_le_workflow_demande_le_droit_decrire(configuration):
    rendu = workflow.render(configuration)
    # Sans cette permission le runner ne peut pas pousser, et aucun secret
    # n'est nécessaire par ailleurs.
    assert "contents: write" in rendu
    assert "secrets." not in rendu


def test_le_fuseau_nest_pose_que_sil_est_connu(configuration):
    assert "TZ:" not in workflow.render(configuration)
    assert "TZ: Europe/Paris" in workflow.render(configuration, timezone="Europe/Paris")


def test_les_jours_sont_rendus_dans_la_forme_attendue_par_les_options(configuration):
    configuration.schedule.days = [0, 1, 2, 3, 4]
    assert workflow.describe_days(configuration) == "lun-ven"
    configuration.schedule.days = [5, 6]
    assert workflow.describe_days(configuration) == "weekend"
    configuration.schedule.days = [0, 2]
    assert workflow.describe_days(configuration) == "lun,mer"


def test_le_journal_dit_quels_creneaux_sont_deja_poses(tmp_path):
    journal = repo.Journal(tmp_path, "journal.md", 1000)
    journal.append("- 2026-09-14 07:05 : Note du jour\n")
    journal.append("- 2026-09-14 07:41 : Point d'étape\n")
    journal.append("- 2026-09-15 07:10 : Reprend le fil\n")
    releve = repo.journal_slots(tmp_path, "journal.md")
    assert releve["2026-09-14"] == {"07:05", "07:41"}
    assert releve["2026-09-15"] == {"07:10"}


def test_le_releve_couvre_toute_la_serie_de_fichiers(tmp_path):
    journal = repo.Journal(tmp_path, "journal.md", 6)
    for minute in range(8):
        journal.append(f"- 2026-09-14 07:{minute:02d} : Note\n")
    assert (tmp_path / "journal-2.md").exists()
    releve = repo.journal_slots(tmp_path, "journal.md")
    assert len(releve["2026-09-14"]) == 8


def test_lentete_nest_pas_pris_pour_un_creneau(tmp_path):
    (tmp_path / "journal.md").write_text("# Journal\n\nTexte libre.\n", encoding="utf-8")
    assert repo.journal_slots(tmp_path, "journal.md") == {}


def test_un_creneau_deja_journalise_nest_pas_recommite(tmp_path, monkeypatch):
    appels: list[list[str]] = []
    monkeypatch.setattr(repo, "run_git", lambda args, **kw: appels.append(args) or "abc1234")

    reglage = conf.Config()
    journal = repo.Journal(tmp_path, "journal.md", 1000)
    journal.append("- 2026-09-14 07:05 : Note du jour\n")

    faits = repo.commit_entries(
        reglage,
        tmp_path,
        [
            (date(2026, 9, 14), "07:05", "Note du jour"),
            (date(2026, 9, 14), "07:41", "Point d'étape"),
        ],
    )
    # Le premier créneau était déjà là : seul le second donne un commit.
    assert [commit.creneau for commit in faits] == ["07:41"]
    assert sum(1 for args in appels if args[0] == "commit") == 1


def test_la_visite_porte_sa_date_de_depart(configuration):
    rendu = workflow.render(configuration, since=date(2026, 9, 15))
    # Sans cette borne, la premiere visite prendrait les sept journees
    # precedentes pour des journees manquees et inventerait une semaine.
    assert "--depuis 2026-09-15" in rendu
