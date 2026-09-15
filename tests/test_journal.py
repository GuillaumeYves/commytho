"""Tests de la rotation du fichier suivi.

Rien ici ne touche à git : on vérifie uniquement le choix du fichier alimenté
et le moment où commytho passe au suivant.
"""

from commytho.repo import Journal, _nom_indexe


def test_le_premier_fichier_garde_le_nom_demande():
    assert _nom_indexe("journal.md", 1) == "journal.md"


def test_les_suivants_sont_numerotes():
    assert _nom_indexe("journal.md", 2) == "journal-2.md"
    assert _nom_indexe("journal.md", 10) == "journal-10.md"


def test_la_numerotation_respecte_les_sous_dossiers():
    assert _nom_indexe("notes/journal.md", 3) == "notes/journal-3.md"


def test_un_fichier_neuf_recoit_un_entete(tmp_path):
    journal = Journal(tmp_path, "journal.md", 1000)
    assert journal.append("- une ligne\n") == "journal.md"
    contenu = (tmp_path / "journal.md").read_text(encoding="utf-8")
    assert contenu.startswith("# Journal")
    assert contenu.endswith("- une ligne\n")


def test_le_seuil_fait_passer_au_fichier_suivant(tmp_path):
    journal = Journal(tmp_path, "journal.md", 10)
    touches = [journal.append(f"- ligne {n}\n") for n in range(12)]
    # L'en-tête compte dans les lignes : le seuil de dix tombe avant la fin.
    assert "journal.md" in touches
    assert "journal-2.md" in touches
    assert touches.index("journal-2.md") > touches.index("journal.md")
    assert len((tmp_path / "journal.md").read_text(encoding="utf-8").splitlines()) <= 10


def test_le_second_fichier_annonce_sa_place_dans_la_serie(tmp_path):
    journal = Journal(tmp_path, "journal.md", 5)
    for n in range(8):
        journal.append(f"- ligne {n}\n")
    assert (tmp_path / "journal-2.md").read_text(encoding="utf-8").startswith("# Journal, suite 2")


def test_la_rotation_reprend_au_dernier_fichier_present(tmp_path):
    (tmp_path / "journal.md").write_text("plein\n", encoding="utf-8")
    (tmp_path / "journal-2.md").write_text("plein\n", encoding="utf-8")
    # Aucun état local n'est consulté : seul le contenu du dépôt fait foi.
    journal = Journal(tmp_path, "journal.md", 1000)
    assert journal.append("- suite\n") == "journal-2.md"


def test_un_seuil_nul_desactive_la_rotation(tmp_path):
    journal = Journal(tmp_path, "journal.md", 0)
    touches = {journal.append(f"- ligne {n}\n") for n in range(50)}
    assert touches == {"journal.md"}
