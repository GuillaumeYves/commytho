"""Tests de l'état quotidien et du choix des messages."""

from datetime import date

from commytho import messages, paths, state


def test_le_changement_de_jour_remet_les_creneaux_a_zero():
    veille = state.State(day="2026-09-13", plan=["09:00"], done=["09:00"], total_commits=7)
    nouveau = state.roll_over(veille, date(2026, 9, 14), ["10:00", "15:00"])
    assert nouveau.day == "2026-09-14"
    assert nouveau.done == []
    assert nouveau.plan == ["10:00", "15:00"]
    # Le cumul, lui, survit au changement de jour.
    assert nouveau.total_commits == 7


def test_le_meme_jour_conserve_les_creneaux_honores():
    courant = state.State(day="2026-09-14", plan=["09:00"], done=["09:00"], total_commits=1)
    identique = state.roll_over(courant, date(2026, 9, 14), ["09:00", "16:00"])
    assert identique.done == ["09:00"]
    assert identique.plan == ["09:00", "16:00"]


def test_aller_retour_sur_disque(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "config_dir", lambda: tmp_path)
    state.save(state.State(day="2026-09-14", plan=["09:00", "12:00"], done=["09:00"]))
    relu = state.load()
    assert relu.done == ["09:00"]
    assert relu.remaining == 1


def test_un_etat_corrompu_repart_a_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    (tmp_path / "state.json").write_text("pas du json", encoding="utf-8")
    assert state.load().day == ""


def test_le_message_est_stable_pour_un_creneau():
    pool = messages.MESSAGES
    jour = date(2026, 9, 14)
    assert messages.pick(pool, jour, "09:00") == messages.pick(pool, jour, "09:00")


def test_deux_creneaux_piochent_independamment():
    pool = [str(n) for n in range(100)]
    jour = date(2026, 9, 14)
    tirages = {messages.pick(pool, jour, f"{h:02d}:00") for h in range(9, 19)}
    # Avec cent messages, dix créneaux ne devraient pas tomber sur le même.
    assert len(tirages) > 1


def test_pool_personnalise(tmp_path):
    fichier = tmp_path / "messages.txt"
    fichier.write_text("# commentaire\npremier\n\nsecond\n", encoding="utf-8")
    assert messages.load_pool(str(fichier)) == ["premier", "second"]


def test_pool_vide_retombe_sur_la_liste_par_defaut(tmp_path):
    fichier = tmp_path / "vide.txt"
    fichier.write_text("\n\n", encoding="utf-8")
    assert messages.load_pool(str(fichier)) == messages.MESSAGES


def test_ligne_de_journal():
    ligne = messages.journal_line(date(2026, 9, 14), "09:47", "Note du jour")
    assert ligne == "- 2026-09-14 09:47 : Note du jour\n"
