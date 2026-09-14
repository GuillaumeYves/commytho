"""Tests de l'analyse des arguments et des gardes-fous du CLI."""

import pytest

from commytho import auth, cli, paths
from commytho import config as conf


@pytest.fixture(autouse=True)
def dossiers_isoles(tmp_path, monkeypatch):
    """Aucun test ne doit toucher la vraie configuration de la machine."""
    monkeypatch.setattr(paths, "config_dir", lambda: tmp_path / "config")
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path / "data")
    monkeypatch.delenv(auth.ENV_VAR, raising=False)
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
