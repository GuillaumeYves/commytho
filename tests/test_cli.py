"""Tests de l'analyse des arguments et des gardes-fous du CLI."""

from datetime import date

import pytest

from commytho import auth, cli, paths
from commytho import config as conf


@pytest.fixture(autouse=True)
def dossiers_isoles(tmp_path, monkeypatch):
    """Aucun test ne doit toucher la configuration ni le trousseau de la machine."""
    monkeypatch.setattr(paths, "config_dir", lambda: tmp_path / "config")
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path / "data")
    monkeypatch.delenv(auth.ENV_VAR, raising=False)
    # Sans ce neutralisant, le trousseau de la machine décide du résultat : un
    # commytho login bien réel suffit à faire échouer le test qui vérifie
    # l'absence de jeton, alors qu'il passe en CI sur une machine vierge.
    monkeypatch.setattr(auth, "_keyring", lambda: None)
    return tmp_path


def test_sans_argument_affiche_laide(capsys):
    assert cli.main([]) == 0
    assert "commytho" in capsys.readouterr().out


def test_up_refuse_sans_depot(capsys):
    assert cli.main(["up"]) == 1
    assert "init" in capsys.readouterr().err


def test_run_refuse_sans_depot(capsys):
    assert cli.main(["run"]) == 1
    assert "init" in capsys.readouterr().err


def test_plan_refuse_sans_depot(capsys):
    assert cli.main(["plan"]) == 1


def test_status_fonctionne_sans_configuration(capsys):
    assert cli.main(["status"]) == 0
    sortie = capsys.readouterr().out
    assert "non configuré" in sortie


def test_up_a_blanc_ninstalle_rien(capsys, monkeypatch):
    configuration = conf.Config()
    configuration.repo = conf.Repo(owner="alice", name="journal")
    conf.save(configuration)
    monkeypatch.setenv(auth.ENV_VAR, "jeton-de-test")

    code = cli.main(["up", "--per-day", "2-4", "--days", "lun-ven", "--dry-run"])
    sortie = capsys.readouterr().out
    assert code == 0
    assert "rien n'a été installé" in sortie
    # L'essai à blanc ne doit pas non plus enregistrer la tâche en config.
    assert conf.load().installed.kind == ""


def test_up_avertit_au_dela_du_plafond_conseille(capsys, monkeypatch):
    configuration = conf.Config()
    configuration.repo = conf.Repo(owner="alice", name="journal")
    conf.save(configuration)
    monkeypatch.setenv(auth.ENV_VAR, "jeton-de-test")

    cli.main(["up", "--max", "60", "--dry-run"])
    assert "rien d'humain" in capsys.readouterr().out


def test_up_refuse_une_expression_de_jours_invalide(capsys, monkeypatch):
    configuration = conf.Config()
    configuration.repo = conf.Repo(owner="alice", name="journal")
    conf.save(configuration)
    monkeypatch.setenv(auth.ENV_VAR, "jeton-de-test")

    assert cli.main(["up", "--days", "lundimanche", "--dry-run"]) == 1


def test_le_jeton_denvironnement_prime(monkeypatch):
    monkeypatch.setenv(auth.ENV_VAR, "jeton-de-test")
    assert auth.retrieve() == "jeton-de-test"


def test_absence_de_jeton_signalee():
    with pytest.raises(auth.AuthError):
        auth.retrieve()


class _HuitHeures:
    """Fige l'heure du réveil, pour que les créneaux testés soient en retard."""

    @staticmethod
    def now():
        from datetime import datetime

        return datetime(2026, 9, 14, 8, 0)

    @staticmethod
    def fromisoformat(valeur):
        from datetime import datetime

        return datetime.fromisoformat(valeur)


class _QuatorzeSeptembre(date):
    """Fige le jour courant, sans quoi la reprise viserait de vraies dates."""

    @classmethod
    def today(cls):
        return date(2026, 9, 14)


@pytest.fixture
def run_prepare(monkeypatch):
    """Prépare un run avec un programme connu et sans toucher à git."""

    def prepare(catch_up: int):
        configuration = conf.Config()
        configuration.repo = conf.Repo(owner="alice", name="journal")
        configuration.schedule.catch_up = catch_up
        conf.save(configuration)
        monkeypatch.setenv(auth.ENV_VAR, "jeton-de-test")
        monkeypatch.setattr(cli, "datetime", _HuitHeures)
        monkeypatch.setattr(cli.planner, "plan_for_day", lambda *args: ["07:05", "07:20", "07:41"])

        recu: list[list[tuple[object, str, str]]] = []

        def faux_commits(config, token, creneaux):
            recu.append(list(creneaux))
            return [f"hash{i}" for i in range(len(creneaux))]

        monkeypatch.setattr(cli.repo, "make_commits", faux_commits)
        return recu

    return prepare


def test_le_rattrapage_complet_rejoue_tous_les_creneaux(run_prepare):
    recu = run_prepare(catch_up=0)
    assert cli.main(["run"]) == 0
    # Machine allumée à 08:00 : les trois créneaux du matin sont rejoués,
    # chacun avec l'horodatage de son créneau.
    assert [creneau for _, creneau, _ in recu[0]] == ["07:05", "07:20", "07:41"]


def test_le_rattrapage_par_defaut_ne_garde_que_le_dernier(run_prepare):
    recu = run_prepare(catch_up=1)
    assert cli.main(["run"]) == 0
    assert [creneau for _, creneau, _ in recu[0]] == ["07:41"]


def test_le_rattrapage_respecte_le_plafond_du_jour(run_prepare):
    recu = run_prepare(catch_up=0)
    configuration = conf.load()
    configuration.schedule.cap_per_day = 2
    conf.save(configuration)
    assert cli.main(["run"]) == 0
    # Le plafond prime sur le rattrapage : on garde les créneaux les plus
    # récents, les plus anciens sont abandonnés.
    assert [creneau for _, creneau, _ in recu[0]] == ["07:20", "07:41"]


def test_la_reprise_solde_les_journees_manquees(monkeypatch):
    """Machine éteinte deux jours, rallumée : l'arriéré part avec les bonnes dates."""
    configuration = conf.Config()
    configuration.repo = conf.Repo(owner="alice", name="journal")
    configuration.schedule.days = list(range(7))
    configuration.schedule.catch_up = 0
    configuration.schedule.catch_up_days = 2
    configuration.installed = conf.Installed(
        kind="schtasks", identifier="commytho", installed_at="2026-09-01T08:00:00"
    )
    conf.save(configuration)
    monkeypatch.setenv(auth.ENV_VAR, "jeton-de-test")
    monkeypatch.setattr(cli, "datetime", _HuitHeures)
    monkeypatch.setattr(cli, "date", _QuatorzeSeptembre)
    monkeypatch.setattr(cli.planner, "plan_for_day", lambda *args: ["07:05", "07:41"])

    # L'avant-veille est la dernière journée vue par commytho, et elle était
    # déjà soldée. La veille, elle, n'a laissé aucune trace.
    cli.state.save(
        cli.state.State(day="2026-09-12", plan=["07:05", "07:41"], done=["07:05", "07:41"])
    )

    recu: list[list[tuple[date, str, str]]] = []

    def faux_commits(config, token, creneaux):
        recu.append(list(creneaux))
        return [f"hash{i}" for i in range(len(creneaux))]

    monkeypatch.setattr(cli.repo, "make_commits", faux_commits)
    assert cli.main(["run"]) == 0

    envoyes = [(jour.isoformat(), creneau) for jour, creneau, _ in recu[0]]
    assert envoyes == [
        ("2026-09-13", "07:05"),
        ("2026-09-13", "07:41"),
        ("2026-09-14", "07:05"),
        ("2026-09-14", "07:41"),
    ]
    # L'avant-veille soldée ne revient pas, et la reprise est notée.
    relu = cli.state.load()
    assert relu.history["2026-09-13"] == ["07:05", "07:41"]
    assert relu.done == ["07:05", "07:41"]


def test_la_reprise_ne_remonte_pas_avant_la_pose_de_la_tache(monkeypatch):
    configuration = conf.Config()
    configuration.repo = conf.Repo(owner="alice", name="journal")
    configuration.schedule.days = list(range(7))
    configuration.schedule.catch_up_days = 7
    configuration.installed = conf.Installed(installed_at="2026-09-14T09:00:00")
    conf.save(configuration)
    monkeypatch.setenv(auth.ENV_VAR, "jeton-de-test")
    monkeypatch.setattr(cli, "datetime", _HuitHeures)
    monkeypatch.setattr(cli, "date", _QuatorzeSeptembre)
    monkeypatch.setattr(cli.planner, "plan_for_day", lambda *args: ["07:05"])

    recu: list[list[tuple[object, str, str]]] = []

    def faux_commits(config, token, creneaux):
        recu.append(list(creneaux))
        return ["hash0"]

    monkeypatch.setattr(cli.repo, "make_commits", faux_commits)
    assert cli.main(["run"]) == 0
    # Une tâche posée le jour même n'invente pas une semaine d'activité.
    assert [jour.isoformat() for jour, _, _ in recu[0]] == ["2026-09-14"]
