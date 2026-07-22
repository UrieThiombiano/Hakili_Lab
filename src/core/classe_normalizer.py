"""Extraction et normalisation de la classe imprimée en en-tête des sujets
Hakili Lab (ligne "EVALUATION {classe}", déjà présente dans la transcription
produite en Phase A — voir docs/decision_register.md).

Fonctions pures, sans effet de bord, testables indépendamment du pipeline.
"""
from __future__ import annotations

import re
import unicodedata

# Programme couvert par Hakili Lab (cf. CLAUDE.md : "Maths 6e à la Tle"), plus
# le primaire (CP, CE, CM) — présent côté enseignants (Sheet réel) même si
# Hakili Lab ne teste pas ces niveaux. Un enseignant du primaire n'aura
# simplement aucun élève accessible (voir meme_niveau ci-dessous) : ce n'est
# pas une erreur, juste une liste vide.
CANONICAL_CLASSES: list[str] = ["CP", "CE", "CM", "6e", "5e", "4e", "3e", "2nde", "1ere", "Tle"]

# Niveaux qui portent une série côté élèves (TleD, 1ereD, 2ndC) — utilisé par
# normalize_classe_avec_serie ci-dessous. Le collège (6e-3e) et le primaire
# n'ont pas de série dans les données réelles.
_NIVEAUX_AVEC_SERIE = {"Tle", "2nde", "1ere"}

_HEADER_RE = re.compile(r"(?im)^\s*EVALUATION\s+(.+?)\s*$")

# Ordre volontaire : Tle avant 1ere pour éviter tout chevauchement sur des
# abréviations courtes ("ts", "td"), même si en pratique aucune collision
# n'existe entre les motifs ci-dessous.
_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bterm(inale)?\b|\btle\b|\bts\b|\btd\b"), "Tle"),
    (re.compile(r"\b1\s*(ere|re)\b|\bpremiere\b"), "1ere"),
    (re.compile(r"\b2\s*n?de?\b|\bseconde\b"), "2nde"),
    (re.compile(r"\b6\s*e(me)?\b|\bsixieme\b"), "6e"),
    (re.compile(r"\b5\s*e(me)?\b|\bcinquieme\b"), "5e"),
    (re.compile(r"\b4\s*e(me)?\b|\bquatrieme\b"), "4e"),
    (re.compile(r"\b3\s*e(me)?\b|\btroisieme\b"), "3e"),
    (re.compile(r"\bcp\b"), "CP"),
    (re.compile(r"\bce\b"), "CE"),
    (re.compile(r"\bcm\b"), "CM"),
]


def _fold(text: str) -> str:
    """Minuscule, sans accents, ponctuation réduite à des espaces."""
    normalized = unicodedata.normalize("NFD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()


def normalize_classe(raw: str | None) -> str | None:
    """Convertit un texte de classe brut (typographié, casse/accents variables)
    vers une valeur canonique parmi CANONICAL_CLASSES.

    Ex : "3ème", "3eme", "3E", "3 e", "Troisième" → "3e"
         "Tle D", "Terminale", "TS"               → "Tle"
         "1ère D", "1re", "Première"               → "1ere"

    Retourne None si aucun motif connu ne correspond — ne jamais deviner.
    """
    if not raw:
        return None
    folded = _fold(raw)
    if not folded:
        return None
    for pattern, canonical in _RULES:
        if pattern.search(folded):
            return canonical
    return None


def extract_raw_classe_header(text: str) -> str | None:
    """Cherche une ligne "EVALUATION {classe}" dans un texte de transcription
    et retourne le texte brut capturé (non normalisé), ou None si absent."""
    if not text:
        return None
    match = _HEADER_RE.search(text)
    return match.group(1).strip() if match else None


def niveaux_to_canonical_list(niveaux: str) -> list[str]:
    """Convertit le champ `niveaux` d'un HakiliTest (ex: "6e · 5e · 4e") en
    liste de classes canoniques. Ignore les tokens non reconnus."""
    if not niveaux:
        return []
    tokens = [t.strip() for t in niveaux.split("·")]
    resolved = [normalize_classe(t) for t in tokens]
    return [c for c in resolved if c]


def normalize_classe_avec_serie(raw: str | None) -> str | None:
    """Comme normalize_classe, mais CONSERVE la série (D, C...) quand le
    texte brut en porte une — utilisé pour la classe des ÉLÈVES (Sheet
    élèves), où la série existe et doit rester affichable.

    Ex : "TleD" → "Tle D", "2ndC" → "2nde C", "1ereD" → "1ere D",
         "3eme" → "3e" (le collège n'a pas de série).

    Distincte de meme_niveau() ci-dessous, qui elle IGNORE la série pour le
    filtre de permission — ne jamais confondre les deux usages : celle-ci
    est pour l'affichage/le stockage, meme_niveau est pour la comparaison.
    """
    if not raw:
        return None
    texte = raw.strip()

    if len(texte) >= 2 and texte[-1].isalpha() and texte[-1].isupper():
        niveau_sans_serie = normalize_classe(texte[:-1])
        if niveau_sans_serie in _NIVEAUX_AVEC_SERIE:
            return f"{niveau_sans_serie} {texte[-1]}"

    return normalize_classe(texte)


def meme_niveau(classe_a: str | None, classe_b: str | None) -> bool:
    """Compare deux classes en ignorant la série ("Tle D" et "Tle"
    correspondent) — utilisé par le FILTRE de permission (enseignant vs
    élève), jamais pour l'affichage (voir normalize_classe_avec_serie
    ci-dessus, qui elle préserve la série).

    normalize_classe() suffit pour extraire le niveau des deux côtés : ses
    motifs sont bornés (\\b...\\b) et s'arrêtent naturellement avant la
    série tant que celle-ci est séparée par un espace dans le texte reçu
    (c'est le format produit par normalize_classe_avec_serie).

    Retourne False si l'un des deux ne correspond à aucun niveau connu —
    jamais un rapprochement approximatif.
    """
    niveau_a = normalize_classe(classe_a)
    niveau_b = normalize_classe(classe_b)
    if niveau_a is None or niveau_b is None:
        return False
    return niveau_a == niveau_b


def resolve_classe(*, extracted: str | None, niveaux_declares: list[str]) -> tuple[str | None, str]:
    """Décide de la classe à écrire en base, en croisant l'extraction avec les
    niveaux déclarés par le test Hakili sélectionné (garde-fou).

    Retourne (classe_ou_None, motif) — motif toujours renseigné pour les logs.
    Règle absolue : ne jamais inventer une classe. None = ne rien écrire.
    """
    if extracted:
        if not niveaux_declares or extracted in niveaux_declares:
            return extracted, "extraction_confirmee"
        return None, (
            f"incoherence : classe extraite '{extracted}' absente des niveaux "
            f"déclarés {niveaux_declares}"
        )
    if len(niveaux_declares) == 1:
        return niveaux_declares[0], "repli_niveau_unique_declare"
    return None, "extraction_echouee_et_niveaux_ambigus_ou_absents"
