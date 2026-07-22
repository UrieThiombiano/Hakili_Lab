from datetime import date
from types import SimpleNamespace

from src.core.tendance import SEUIL_TENDANCE, calculer_tendance


def _copie(notes_finales, date_soumission):
    return SimpleNamespace(notes_finales=notes_finales, date_soumission=date_soumission)


# ── Cas nominaux ────────────────────────────────────────────────────────────

def test_progression_nette():
    copies = [_copie(10.0, date(2026, 1, 1)), _copie(13.0, date(2026, 2, 1))]
    assert calculer_tendance(copies) == "progresse"


def test_regression():
    copies = [_copie(14.0, date(2026, 1, 1)), _copie(11.0, date(2026, 2, 1))]
    assert calculer_tendance(copies) == "regresse"


def test_stagnation_ecart_inferieur_au_seuil():
    copies = [_copie(12.0, date(2026, 1, 1)), _copie(12.5, date(2026, 2, 1))]
    assert calculer_tendance(copies) == "stagne"


# ── Cas insuffisants (gris) ──────────────────────────────────────────────────

def test_une_seule_copie_insuffisant():
    copies = [_copie(15.0, date(2026, 1, 1))]
    assert calculer_tendance(copies) == "insuffisant"


def test_zero_copie_insuffisant():
    assert calculer_tendance([]) == "insuffisant"


def test_note_null_ignoree():
    """Une copie NULL (en cours de traitement) ne compte pas comme une note
    -- avec une seule copie réellement notée, le cas doit rester
    "insuffisant", pas planter ni compter la copie NULL comme une 2e note."""
    copies = [
        _copie(None, date(2026, 1, 1)),
        _copie(15.0, date(2026, 2, 1)),
    ]
    assert calculer_tendance(copies) == "insuffisant"


def test_note_null_ignoree_avec_assez_de_notes_valides():
    """Trois copies, une NULL au milieu : les deux dernières NOTÉES doivent
    être comparées (2026-01-01 et 2026-03-01), pas la NULL du 02-01."""
    copies = [
        _copie(10.0, date(2026, 1, 1)),
        _copie(None, date(2026, 2, 1)),
        _copie(13.0, date(2026, 3, 1)),
    ]
    assert calculer_tendance(copies) == "progresse"


# ── Bornes exactes du seuil ──────────────────────────────────────────────────

def test_ecart_exactement_au_seuil_progresse():
    copies = [_copie(10.0, date(2026, 1, 1)), _copie(10.0 + SEUIL_TENDANCE, date(2026, 2, 1))]
    assert calculer_tendance(copies) == "progresse"


def test_ecart_exactement_au_seuil_regresse():
    copies = [_copie(10.0, date(2026, 1, 1)), _copie(10.0 - SEUIL_TENDANCE, date(2026, 2, 1))]
    assert calculer_tendance(copies) == "regresse"


def test_ordre_entree_quelconque_trie_par_date():
    """L'ordre d'entree ne doit pas influencer le resultat -- le tri se fait
    sur date_soumission, pas sur l'ordre de la liste."""
    copies = [_copie(13.0, date(2026, 2, 1)), _copie(10.0, date(2026, 1, 1))]
    assert calculer_tendance(copies) == "progresse"
