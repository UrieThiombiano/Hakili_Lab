"""
Découpage structurel des textes LLM en (intro, items numérotés).

Problème résolu ici, une fois pour toutes
─────────────────────────────────────────
Les textes libres produits par les LLM (énoncés d'exercices, plans de
remédiation) mélangent fréquemment DEUX systèmes de numérotation dans une
même chaîne : "(1) … (2) … (3) …" inline ET "\n1. … \n2. …" — avec
redémarrages, sauts et entrelacements. Toute approche qui exige une séquence
1, 2, 3, … parfaite échoue sur ces hybrides, et toute approche qui préserve
le texte verbatim laisse les marqueurs sources entrer en collision avec la
numérotation régénérée par le template.

Principe de ce module — deux invariants :

1. **Les numéros écrits par le LLM ne sont pas fiables ; seule la POSITION
   des marqueurs fait foi.** Chaque marqueur ouvre un nouvel item, dans
   l'ordre de lecture, quel que soit le numéro qu'il prétend porter.

2. **Une seule numérotation doit survivre dans le PDF : celle du template.**
   Aucun marqueur source ("(1)", "2.", "3)") ne subsiste dans l'intro ni
   dans les items retournés — le template numérote via <ol>/loop.index.

Ce module est volontairement le SEUL endroit où vivent la détection et la
suppression des marqueurs : pdf_report_html et pdf_remediation_html
l'utilisent tous les deux.
"""
from __future__ import annotations

import re

# Marqueur de numérotation : "(n)", "n." ou "n)" —
#   - à une frontière de phrase/ligne ([.!?;:] ou \n ou début de texte),
#     jamais en pleine phrase ("mesure 40" ne doit pas matcher) ;
#   - 1 ou 2 chiffres maximum (élimine les années : "En 2020. ") ;
#   - suivi d'un blanc puis d'un non-chiffre (élimine "3. 5" décimal anglais) ;
#   - "(1 m = 1000 mm)" ne matche pas : il faut ")" ou "." collé au nombre.
_MARKER = re.compile(
    r"(?:\A|(?<=[.!?;:])|(?<=\n))"      # frontière
    r"[ \t]*"
    r"(?:\((\d{1,2})\)|(\d{1,2})[.)])"  # (n) | n. | n)
    r"\s+(?![0-9])"
)

# Garde anti-référence : "Num. 4", "Geo. 7" (produits par _humanize_ids_in_text)
# sont des RÉFÉRENCES à une question — leur point est intrinsèque à
# l'abréviation et fournirait une fausse frontière au marqueur suivant
# ("… la question Num. 4. Ensuite …"). Les références en toutes lettres
# ("question 2", "exercice 3") ne peuvent pas matcher _MARKER : aucune
# frontière de phrase ne précède leur nombre — pas besoin de les garder ici,
# et les inclure rejetterait à tort les vraies listes après une phrase se
# terminant par ces mots ("Contexte du problème. 1. Fais …").
_REF_BEFORE = re.compile(r"(?:\bNum|\bG[ée]o)\.?\s*$", re.IGNORECASE)

# Marqueur résiduel collé en tête d'un item ("(1) 1. Justifie…") — supprimé
# itérativement pour garantir l'invariant n°2.
_LEADING_RESIDUAL = re.compile(r"^\(?\d{1,2}[.)][ \t]+(?![0-9])")


def _marker_number(m: re.Match) -> int:
    return int(m.group(1) or m.group(2))


def _is_reference(text: str, m: re.Match) -> bool:
    return bool(_REF_BEFORE.search(text[: m.start()]))


def split_numbered_items(text: str) -> tuple[str, list[str]]:
    """
    Découpe un texte LLM en (intro, [item1, item2, …]) sur ses marqueurs de
    numérotation, dans l'ordre de lecture, en ignorant les numéros portés.

    Retourne (text, []) si aucune liste n'est détectée. L'intro peut être ""
    si le texte démarre directement sur un marqueur. Les items retournés ne
    contiennent plus aucun marqueur en tête — la numérotation visible doit
    être régénérée par l'appelant (template <ol> / loop.index).
    """
    matches = [m for m in _MARKER.finditer(text) if not _is_reference(text, m)]
    if not matches:
        return text, []

    # Un marqueur isolé n'est une liste que s'il annonce un début ("1"/"(1)").
    # Un "(3)" seul est plus probablement une scorie — on ne découpe pas.
    if len(matches) == 1 and _marker_number(matches[0]) != 1:
        return text, []

    intro = text[: matches[0].start()].strip()

    items: list[str] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        seg = text[m.end(): end].strip().rstrip(";").strip()
        # Invariant n°2 : aucun marqueur résiduel en tête d'item
        while True:
            stripped = _LEADING_RESIDUAL.sub("", seg).strip()
            if stripped == seg:
                break
            seg = stripped
        if seg:
            items.append(seg)

    if not items:
        return text, []
    return intro, items
