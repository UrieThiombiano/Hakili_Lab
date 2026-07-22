"""Normalisation du texte libre saisi dans la colonne "centre" des Google
Sheets (élèves et personnel), et dérivation dynamique de la liste des
centres réels à partir des données — il n'existe plus de liste figée dans le
code (CENTRES_AUTORISES a été retirée) : ajouter un centre se fait
désormais dans les Sheets, jamais dans ce fichier.

La normalisation tolère les différences ANODINES (espaces superflus, casse,
accents : " tampouy ", "TAMPOUY" → "Tampouy") mais ne corrige jamais une
vraie faute de frappe ("Tampuy" reste "Tampuy", distinct de "Tampouy") — la
détection de ce genre de divergence se fait par comptage (voir
deriver_centres ci-dessous), pas par correction automatique.

Même esprit que src/core/classe_normalizer.py (fonctions pures, testables).
"""
from __future__ import annotations

import re
import unicodedata

# Un centre vu ce nombre de fois ou moins (élèves + personnel confondus) est
# signalé "suspect" (faute de frappe possible) — jamais bloqué, jamais
# corrigé automatiquement, juste une alerte discrète côté admin. Constante
# nommée pour rester ajustable si besoin (ex. la relever à 2).
SEUIL_CENTRE_SUSPECT = 1


def fold_centre(text: str) -> str:
    """Minuscule, sans accents, espaces superflus réduits — tolère la casse
    et les espaces mais ne touche à aucune lettre : une vraie faute de frappe
    donne un résultat différent, par construction."""
    normalized = unicodedata.normalize("NFD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"\s+", " ", ascii_text).strip()


def centres_correspondent(a: str | None, b: str | None) -> bool:
    """Compare deux valeurs de centre en tolérant casse/accents/espaces —
    même normalisation que la lecture des Sheets et que la dérivation
    dynamique ci-dessous (deriver_centres), à réutiliser partout où deux
    centres sont comparés (permissions incluses) : lecture, affichage et
    permissions doivent toujours s'appuyer sur la même forme repliée, sous
    peine de faire apparaître un élève d'un côté et le refuser de l'autre.

    Si l'un des deux (ou les deux) est vide, on replie sur une égalité texte
    stricte (après un simple strip) plutôt que de faire correspondre deux
    valeurs vides sans rapport entre elles."""
    fa, fb = fold_centre(a or ""), fold_centre(b or "")
    if fa and fb:
        return fa == fb
    return (a or "").strip() == (b or "").strip()


def deriver_centres(valeurs_brutes: list[str]) -> dict[str, dict]:
    """Construit la liste des centres réels à partir de TOUTES les valeurs
    "centre" vues dans les Sheets (élèves ET personnel), en regroupant les
    variations anodines (casse/accents/espaces) sous une forme commune.

    Retourne {forme_repliee: {"canonique": str, "count": int, "suspect": bool}}
    — "canonique" est la graphie la plus fréquente pour cette forme repliée
    (égalité → la première rencontrée) ; "suspect" est vrai si ce centre n'a
    été vu que SEUIL_CENTRE_SUSPECT fois ou moins (élèves + personnel
    confondus) — signal d'une faute de frappe possible, jamais un rejet."""
    par_forme_repliee: dict[str, dict] = {}
    for brut in valeurs_brutes:
        brut = (brut or "").strip()
        if not brut:
            continue
        cle = fold_centre(brut)
        entree = par_forme_repliee.setdefault(cle, {"count": 0, "variantes": {}})
        entree["count"] += 1
        entree["variantes"][brut] = entree["variantes"].get(brut, 0) + 1

    resultat: dict[str, dict] = {}
    for cle, entree in par_forme_repliee.items():
        canonique = max(entree["variantes"].items(), key=lambda kv: kv[1])[0]
        resultat[cle] = {
            "canonique": canonique,
            "count": entree["count"],
            "suspect": entree["count"] <= SEUIL_CENTRE_SUSPECT,
        }
    return resultat
