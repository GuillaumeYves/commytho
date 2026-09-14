"""Tests de l'analyse des arguments et des gardes-fous du CLI."""

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

        recu: list[list[tuple[str, str]]] = []

        def faux_commits(config, token, jour, creneaux):
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
    assert [creneau for creneau, _ in recu[0]] == ["07:05", "07:20", "07:41"]


def test_le_rattrapage_par_defaut_ne_garde_que_le_dernier(run_prepare):
    recu = run_prepare(catch_up=1)
    assert cli.main(["run"]) == 0
    assert [creneau for creneau, _ in recu[0]] == ["07:41"]


def test_le_rattrapage_respecte_le_plafond_du_jour(run_prepare):
    recu = run_prepare(catch_up=0)
    configuration = conf.load()
    configuration.schedule.cap_per_day = 2
    conf.save(configuration)
    assert cli.main(["run"]) == 0
    # Le plafond prime sur le rattrapage : on garde les créneaux les plus
    # récents, les plus anciens sont abandonnés.
    assert [creneau for creneau, _ in recu[0]] == ["07:20", "07:41"]
