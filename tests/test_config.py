"""Tests de la lecture des options et de la persistance de la configuration."""

import json

import pytest

from commytho import config as conf
from commytho import paths


def test_jours_nommes():
    assert conf.parse_days("lun,mer,ven") == [0, 2, 4]


def test_plage_de_jours():
    assert conf.parse_days("lun-ven") == [0, 1, 2, 3, 4]


def test_plage_qui_enjambe_le_dimanche():
    assert conf.parse_days("ven-lun") == [0, 4, 5, 6]


def test_raccourcis_de_jours():
    assert conf.parse_days("tous") == [0, 1, 2, 3, 4, 5, 6]
    assert conf.parse_days("weekend") == [5, 6]
    assert conf.parse_days("semaine") == [0, 1, 2, 3, 4]


def test_noms_anglais_acceptes():
    assert conf.parse_days("mon-fri") == [0, 1, 2, 3, 4]


def test_jour_inconnu_refuse():
    with pytest.raises(conf.ConfigError):
        conf.parse_days("lundi")


def test_frequence_simple_et_intervalle():
    assert conf.parse_range("3") == (3, 3)
    assert conf.parse_range("1-4") == (1, 4)


def test_frequence_incoherente_refusee():
    with pytest.raises(conf.ConfigError):
        conf.parse_range("5-2")


def test_plage_horaire_normalisee():
    assert conf.parse_window("9:00-19:30") == ("09:00", "19:30")


def test_plage_horaire_a_lenvers_refusee():
    with pytest.raises(conf.ConfigError):
        conf.parse_window("19:00-09:00")


def test_heure_hors_limites_refusee():
    with pytest.raises(conf.ConfigError):
        conf.parse_window("09:00-25:00")


def test_aller_retour_sur_disque(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)

    configuration = conf.Config()
    configuration.repo = conf.Repo(owner="alice", name="journal", branch="main")
    configuration.schedule.days = [1, 3]
    conf.save(configuration)

    relue = conf.load()
    assert relue.repo.full_name == "alice/journal"
    assert relue.schedule.days == [1, 3]


def test_les_cles_inconnues_sont_ignorees(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    (tmp_path / "config.json").write_text(
        json.dumps({"version": 99, "repo": {"owner": "alice", "name": "x", "futur": 1}}),
        encoding="utf-8",
    )
    relue = conf.load()
    assert relue.repo.owner == "alice"


def test_configuration_illisible_signalee(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "config_dir", lambda: tmp_path)
    (tmp_path / "config.json").write_text("{ pas du json", encoding="utf-8")
    with pytest.raises(conf.ConfigError):
        conf.load()


def test_url_du_depot():
    depot = conf.Repo(owner="alice", name="journal")
    assert depot.https_url == "https://github.com/alice/journal.git"
