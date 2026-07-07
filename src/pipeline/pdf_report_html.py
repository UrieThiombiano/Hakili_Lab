"""
Generation PDF via xhtml2pdf (HTML+CSS -> PDF, pur Python).
Dependance : xhtml2pdf (base sur reportlab, deja installe).
Unicode: Arial standard ne couvre pas tous les symboles mathematiques.
Les textes AI sont normalises avant rendu (_clean).
"""
from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

from markupsafe import Markup

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"

_MONTHS_FR = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def _today_fr() -> str:
    d = date.today()
    return f"{d.day} {_MONTHS_FR[d.month]} {d.year}"

# ── Police Unicode ─────────────────────────────────────────────────────────────
# Priorite : Arial Unicode MS (Office), Segoe UI Symbol (Win10+), Arial standard

_FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\arialuni.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
    (r"C:\Windows\Fonts\seguisym.ttf", r"C:\Windows\Fonts\seguisym.ttf"),
    (r"C:\Windows\Fonts\arial.ttf",    r"C:\Windows\Fonts\arialbd.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/freefont/FreeSans.ttf",
     "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
]

_font_ready = False
_font_css_name = "Helvetica"


def _register_unicode_font() -> str:
    """Enregistre une police TTF Unicode via ReportLab. Retourne son nom CSS."""
    global _font_ready, _font_css_name
    if _font_ready:
        return _font_css_name
    _font_ready = True
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.pdfmetrics import registerFontFamily
        from reportlab.pdfbase.ttfonts import TTFont

        for regular, bold in _FONT_CANDIDATES:
            if Path(regular).exists():
                pdfmetrics.registerFont(TTFont("HakFont", regular))
                bold_path = bold if Path(bold).exists() else regular
                pdfmetrics.registerFont(TTFont("HakFont-Bold", bold_path))
                registerFontFamily("HakFont", normal="HakFont", bold="HakFont-Bold")
                _font_css_name = "HakFont"
                logger.info("Police Unicode enregistree depuis %s", regular)
                break
    except Exception as exc:
        logger.warning("Police Unicode introuvable (%s) -- fallback Helvetica", exc)
    return _font_css_name


# ── Normalisation texte ────────────────────────────────────────────────────────

_ID_NUM = re.compile(r"^Q_NUM_0*(\d+[a-z]?)$", re.IGNORECASE)
_ID_GEO = re.compile(r"^Q_GEO_0*(\d+[a-z]?)$", re.IGNORECASE)
_ID_IN_TEXT = re.compile(r"Q_(?:NUM|GEO)_0*(\d+[a-z]?)", re.IGNORECASE)

# Symboles Unicode hors répertoire WGL4 -- remplacement PDF-safe.
# WGL4 est le socle commun à TOUTES les polices candidates (Arial, Segoe,
# Arial Unicode, Liberation, DejaVu) : ≤ ≥ ≠ ≈ ± × ÷ − √ ∞ ° π → ← ≡ et le
# grec de base y figurent et sont donc CONSERVÉS tels quels (notation maths).
# Seuls les symboles absents de WGL4 sont remplacés — et en français lisible
# par un élève, jamais en jargon informatique.
_MATH_SAFE: dict[str, str] = {
    # Ensembles de nombres (Letterlike Symbols U+2100-U+214F, hors WGL4)
    "ℕ": "N",  # N (naturels)
    "ℤ": "Z",  # Z (entiers)
    "ℚ": "Q",  # Q (rationnels)
    "ℝ": "R",  # R (reels)
    "ℂ": "C",  # C (complexes)
    "ℙ": "P",  # P (premiers)
    # Vecteurs — flèches combinantes (U+20D0–U+20FF) non rendues par les polices PDF
    "⃗": "",   # COMBINING RIGHT ARROW ABOVE (vecteur AB⃗ → AB)
    "⃖": "",   # COMBINING LEFT ARROW ABOVE
    "⃡": "",   # COMBINING LEFT RIGHT ARROW ABOVE
    # Doubles flèches (hors WGL4) — la simple flèche → est dans WGL4
    "⇒": " → ",
    "⇔": " équivaut à ",
    # Operateurs ensemblistes (hors WGL4) — en français élève, pas en ASCII
    "∈": " appartient à ",
    "∉": " n'appartient pas à ",
    "⊂": " inclus dans ",
    "⊆": " inclus dans ",
    "∪": " U ",      # union — notation orale "U" standard au collège
    "∩": " inter ",  # intersection — notation orale standard
    # Multiplication par point (U+22C5 hors WGL4) → croix du collège
    "⋅": " × ",
    # Angles et geometrie (hors WGL4) — vocabulaire français
    "∠": "angle ",
    "⊥": " perpendiculaire à ",
    "∥": " // ",  # notation // écrite en classe
}


# Exposants (U+2070-U+209F) et indices (U+2080-U+2089) Unicode : traités par
# SÉQUENCE pour que "2⁻²" → "2^-2" et "2²¹" → "2^21" (un seul <sup> au rendu),
# et non caractère par caractère ("2^-^2").
_SUPER_MAP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ⁺⁻", "0123456789n+-")
_SUBSC_MAP = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_SUPER_RUN = re.compile("[⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ⁺⁻]+")
_SUBSC_RUN = re.compile("[₀₁₂₃₄₅₆₇₈₉]+")


def _safe_text(s: str) -> str:
    """Remplace les symboles Unicode que la police PDF ne peut pas rendre."""
    s = _SUPER_RUN.sub(lambda m: "^" + m.group(0).translate(_SUPER_MAP), s)
    s = _SUBSC_RUN.sub(lambda m: "_" + m.group(0).translate(_SUBSC_MAP), s)
    for char, repl in _MATH_SAFE.items():
        s = s.replace(char, repl)
    # Les remplacements français (" appartient à ") peuvent doubler les espaces
    return re.sub(r" {2,}", " ", s)


def _humanize_ids_in_text(s: str) -> str:
    """Remplace Q_NUM_04, Q_GEO_07 par 'Num. 4', 'Geo. 7' dans du texte libre."""
    def _repl(m: re.Match) -> str:
        full = m.group(0).upper()
        num = m.group(1)
        return f"Num. {num}" if "NUM" in full else f"Geo. {num}"
    return _ID_IN_TEXT.sub(_repl, s)


def _clean(s: str) -> str:
    """Normalise un texte AI : IDs lisibles + symboles PDF-safe."""
    return _safe_text(_humanize_ids_in_text(s))


# ── Conversion notation mathématique ASCII → HTML ─────────────────────────────
# Deux passes :
#   A. _ascii_math_upgrade : les notations INFORMATIQUES produites par les LLM
#      malgré les consignes ("<=", ">=", "=>", "->", "**", "!=", "* " espacé,
#      commandes LaTeX résiduelles) sont promues en symboles mathématiques
#      WGL4 (≤ ≥ → ≠ × ≈), AVANT échappement HTML — elles contiennent < et >.
#   B. conversions structurelles (après échappement HTML) :
#      sqrt(expr) → √expr | (a/b) et a/b → fraction <sup>a</sup>⁄<sub>b</sub>
#      x^2, x^-2, x^(n+1) → <sup> | u_1, x_A → <sub> | pi → π

_SUP  = re.compile(r'\^(\{[^{}]*\}|\([^()]*\)|[+-]?[A-Za-z0-9]+|[+-])')
_SQRT = re.compile(r'sqrt\(((?:[^()]*|\([^()]*\))*)\)', re.IGNORECASE)
_FRAC = re.compile(r'\((\d+)/(\d+)\)')
# Fraction nue "7/12" : 1-3 chiffres / 1-4 chiffres, jamais adjacente à un
# autre chiffre, un slash, un point ou une virgule (protège les dates
# "06/07/2026", les couples d'années "2025/2026" et les décimaux).
_FRAC_BARE = re.compile(r'(?<![\d/.,_])(\d{1,3})/(\d{1,4})(?![\d/])')
# Indice : lettre isolée + underscore + 1-2 alphanumériques ("u_1", "x_A").
# La lettre doit être un mot d'une lettre (\b) — "copy_id" ne matche pas.
_SUB = re.compile(r'\b([A-Za-z])_([A-Za-z0-9]{1,2})\b')

# Exposants écrits sans caret par l'IA malgré la consigne "a^n" -- l'IA écrit parfois
# "cm2"/"R2" au lieu de "cm^2"/"R^2". Ces deux familles sont sans ambiguïté dans ce
# domaine (unités d'aire/volume, rayon/diamètre au carré) contrairement à un exposant
# générique sur une lettre isolée (ex: u2 pourrait être un indice de suite u_n).
_UNIT_POW = re.compile(r'\b([cdk]?m)(2|3)\b')
_GEOM_POW = re.compile(r'\b(Rayon|rayon|Diam[eè]tre|diam[eè]tre|R|D)(2|3)\b')
_SUP_DIGIT = {"2": "²", "3": "³"}

# Commandes LaTeX résiduelles (défense en profondeur — les prompts imposent
# l'ASCII mais un provider peut fuiter du LaTeX)
_LATEX_FRAC = re.compile(r'\\[dt]?frac\{([^{}]+)\}\{([^{}]+)\}')
_LATEX_SQRT = re.compile(r'\\sqrt\{([^{}]+)\}')
_LATEX_SIMPLE = [
    (r'\times', '×'), (r'\cdot', '×'), (r'\div', '÷'), (r'\pi', 'π'),
    (r'\leq', '≤'), (r'\geq', '≥'), (r'\neq', '≠'),
    (r'\le', '≤'), (r'\ge', '≥'), (r'\ne', '≠'), (r'\infty', '∞'),
]


def _ascii_math_upgrade(s: str) -> str:
    """Notations informatiques → symboles mathématiques (avant échappement)."""
    # LaTeX résiduel → formes ASCII/Unicode gérées en aval
    s = _LATEX_FRAC.sub(r'(\1/\2)', s)
    s = _LATEX_SQRT.sub(r'sqrt(\1)', s)
    for cmd, sym in _LATEX_SIMPLE:
        s = s.replace(cmd, sym)
    # Comparaisons et flèches — l'ordre compte : <=> avant <= et =>
    s = re.sub(r'\s*<=>\s*', ' équivaut à ', s)
    s = re.sub(r'\s*<=\s*', ' ≤ ', s)
    s = re.sub(r'\s*>=\s*', ' ≥ ', s)
    s = re.sub(r'\s*(?:=>|->)\s*', ' → ', s)
    s = re.sub(r'\s*(?:=/=|!=)\s*', ' ≠ ', s)
    # Gras markdown résiduel "**texte**" → texte (avant la règle puissance)
    s = re.sub(r'\*\*([^*\n]{1,80})\*\*', r'\1', s)
    # Puissance Python "2**3" → "2^3" (rendue en <sup> ensuite)
    s = s.replace('**', '^')
    # "~" d'approximation entre deux valeurs → ≈
    s = re.sub(r'(?<=[\s\d])~(?=\s?\d)', '≈', s)
    # Multiplication : "*" adjacent ou espacé entre termes → ×
    s = re.sub(r'(?<=[A-Za-z0-9)])\*(?=[A-Za-z0-9(])', '×', s)
    s = re.sub(r'(?<=[A-Za-z0-9)])\s+\*\s+(?=[A-Za-z0-9(])', ' × ', s)
    return s


def _math_to_html(s: str) -> str:
    """Convertit les notations mathématiques en HTML lisible.

    Échappe systématiquement & < > AVANT d'insérer les balises <sup>/<sub> :
    le résultat est marqué Markup par les appelants, tout caractère HTML
    brut résiduel du texte LLM casserait le rendu xhtml2pdf.
    """
    s = _ascii_math_upgrade(s)
    s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # 0. Exposants sans caret sur unités/rayon/diamètre → notation en exposant
    s = _UNIT_POW.sub(lambda m: m.group(1) + _SUP_DIGIT[m.group(2)], s)
    s = _GEOM_POW.sub(lambda m: m.group(1) + _SUP_DIGIT[m.group(2)], s)

    def _sup_repl(m: re.Match) -> str:
        inner = m.group(1)
        if (inner.startswith('{') and inner.endswith('}')) or \
           (inner.startswith('(') and inner.endswith(')')):
            inner = inner[1:-1]
        inner = inner.replace('*', '×')
        return f'<sup>{inner}</sup>'

    # 1. sqrt(expr) → √expr  ou  √(expr) si l'expression est composée
    def _repl_sqrt(m: re.Match) -> str:
        inner = m.group(1).strip()
        inner = re.sub(r'(?<=[A-Za-z0-9])\*(?=[A-Za-z0-9])', '×', inner)
        inner = _SUP.sub(_sup_repl, inner)
        if re.match(r'^[A-Za-z0-9]+$', inner):
            return f'√{inner}'
        return f'√({inner})'

    s = _SQRT.sub(_repl_sqrt, s)

    # 2. Exposants x^2, x^-2, x^{n+1}, x^(n+1) → <sup>…</sup>
    #    (avant les fractions : dans "2^3/2^5", le "3/2" ne doit pas devenir
    #    une fraction — une fois les <sup> posés, il n'y a plus d'ambiguïté)
    s = _SUP.sub(_sup_repl, s)

    # 3. Fractions : "(a/b)" puis fractions nues "a/b"
    frac_html = lambda m: f'<sup>{m.group(1)}</sup>&frasl;<sub>{m.group(2)}</sub>'
    s = _FRAC.sub(frac_html, s)
    s = _FRAC_BARE.sub(frac_html, s)

    # 4. Indices u_1, x_A → <sub>
    s = _SUB.sub(r'\1<sub>\2</sub>', s)

    # 5. pi isolé → π
    s = re.sub(r'\bpi\b', 'π', s)

    return s


def _cm(s: str) -> str:
    """_clean + _math_to_html, marqué Markup (HTML sûr pour Jinja2 autoescape)."""
    return Markup(_math_to_html(_clean(s)))


# ── Mise en forme des textes IA denses (diagnostic, remédiation) ──────────────
# Les textes générés par l'IA (causes cachées, plans de remédiation) sont de longs
# paragraphes bruts. Sans découpage, ils s'affichent comme un bloc unique illisible.

_SENT_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ])')

# Le découpage des listes numérotées ("… : 1) … ; 2) …", "…:\n1. …\n2. …",
# formats hybrides mélangés par les LLM) est centralisé dans
# text_structuring.split_numbered_items : marqueurs = frontières
# positionnelles, numéros sources ignorés et supprimés, numérotation
# régénérée par le template. Les références "(Num. 4)" / "(Geo. 7)" issues
# de _humanize_ids_in_text sont protégées par la garde anti-référence.
from src.pipeline.text_structuring import split_numbered_items as _split_steps


def _numbered_list_html(intro: str, steps: list[str]) -> Markup:
    """Rend (intro, items) en <p> + <ol> — l'unique numérotation visible."""
    parts = []
    if intro.strip():
        parts.append(f"<p>{_math_to_html(intro.strip())}</p>")
    parts.append("<ol class='step-list'>")
    parts.extend(f"<li>{_math_to_html(step)}</li>" for step in steps)
    parts.append("</ol>")
    return Markup("".join(parts))


def _paragraphs(s: str) -> Markup:
    """Découpe un texte dense en paragraphes ; si le texte contient une liste
    numérotée (même hybride), elle est rendue en <ol> — jamais en marqueurs bruts."""
    cleaned = _clean(s)
    intro, steps = _split_steps(cleaned)
    if steps:
        return _numbered_list_html(intro, steps)
    sentences = [p.strip() for p in _SENT_SPLIT.split(cleaned) if p.strip()]
    if len(sentences) <= 1:
        return Markup(_math_to_html(cleaned))
    return Markup("".join(f"<p>{_math_to_html(p)}</p>" for p in sentences))


def _action_html(s: str) -> Markup:
    """Rend un plan d'action : liste numérotée <ol> si détectée, sinon paragraphes."""
    cleaned = _clean(s)
    intro, steps = _split_steps(cleaned)
    if not steps:
        return _paragraphs(s)
    return _numbered_list_html(intro, steps)


def _display_id(rid: str) -> str:
    """Q_NUM_04 -> 'Num. 4', Q_GEO_03a -> 'Geo. 3a', autres -> inchanges."""
    m = _ID_NUM.match(rid)
    if m:
        return f"Num. {m.group(1)}"
    m = _ID_GEO.match(rid)
    if m:
        return f"Geo. {m.group(1)}"
    return rid


# ── Formatage ──────────────────────────────────────────────────────────────────

def _fmt(v: float) -> str:
    """Formate un score -- virgule decimale francaise."""
    s = str(int(v)) if v == int(v) else f"{v:g}"
    return s.replace(".", ",")


def _effective_score(q: Any) -> float:
    try:
        if q.teacher_decision.value == "refused" and q.teacher_score is not None:
            return float(q.teacher_score)
    except AttributeError:
        pass
    return float(q.score)


# ── Contexte Jinja2 ────────────────────────────────────────────────────────────

def _build_context(
    copy_id: str,
    grade: Any,
    diagnostic: Any,
    student_name: str,
    rubric: Any = None,
) -> dict[str, Any]:
    """Construit le contexte de rendu -- valeurs brutes, HTML-echappees par Jinja2."""
    questions = grade.questions
    avg_conf = (sum(q.confidence for q in questions) / len(questions)) if questions else 0.0
    n_review = sum(1 for q in questions if q.requires_review)

    final_score    = grade.final_score    if grade.final_score    is not None else grade.total_score
    final_score_20 = grade.final_score_on_20
    _denom = grade.total_possible
    pct = (final_score / _denom) if _denom else 0.0

    rubric_pts: dict[str, float] = {}
    if rubric:
        rubric_pts = {item.id: item.max_score for item in (rubric.items or [])}

    good_qs: list[dict] = []
    bad_qs:  list[dict] = []
    for q in questions:
        ms  = rubric_pts.get(q.rubric_item_id, 1.0)
        eff = _effective_score(q)
        entry = {
            "id":        _display_id(q.rubric_item_id),
            "score_fmt": _fmt(eff),
            "max_fmt":   _fmt(ms),
            "conf_pct":  round(q.confidence * 100),
            "comment":   _cm(q.comment or ""),
            "observed":  _cm(q.observed_answer or "--"),
            "correct":   _cm(q.correct_answer  or "--"),
            "review":    q.requires_review,
        }
        (good_qs if eff > 0 else bad_qs).append(entry)

    skills: list[dict] = []
    if diagnostic and diagnostic.skills:
        for sk in diagnostic.skills:
            skills.append({
                "name":     _cm(sk.name),
                "level":    sk.level,
                "evidence": _cm(sk.evidence),
            })

    root_causes: list[dict] = []
    if diagnostic and diagnostic.root_causes:
        for rc in diagnostic.root_causes:
            root_causes.append({
                "visible": _paragraphs(rc.visible_error),
                "hidden":  _paragraphs(rc.hidden_cause),
                "qs":      ", ".join(_display_id(q) for q in rc.linked_questions) or "--",
            })

    remediation: list[dict] = []
    if diagnostic and diagnostic.remediation_plan:
        for item in sorted(diagnostic.remediation_plan, key=lambda x: x.priority):
            remediation.append({
                "priority": item.priority,
                "topic":    _cm(item.topic),
                "action":   _action_html(item.action),
            })

    is_perfect = (final_score_20 or 0) >= 20.0

    return {
        "STUDENT_NAME":      student_name or copy_id,
        "COPY_ID":           copy_id,
        "DATE":              _today_fr(),
        "FINAL_SCORE":       _fmt(final_score),
        "FINAL_SCORE_20":    _fmt(final_score_20) if final_score_20 is not None else "--",
        "TOTAL_POSSIBLE":    _fmt(grade.total_possible),
        "AI_CONFIDENCE_PCT": round(avg_conf * 100),
        "REVIEW_COUNT":      n_review,
        "SCORE_PCT":         pct,
        "good_questions":    good_qs,
        "bad_questions":     bad_qs,
        "strengths":         [_cm(s) for s in (diagnostic.strengths  if diagnostic else [])],
        "weaknesses":        [_cm(s) for s in (diagnostic.weaknesses if diagnostic else [])],
        "skills":            skills,
        "root_causes":       root_causes,
        "remediation":       remediation,
        "has_diagnostic":    bool(diagnostic),
        "is_perfect_score":  is_perfect,
    }


# ── API publique ───────────────────────────────────────────────────────────────

def generate_copy_report(
    output_path: Path,
    copy_id: str,
    grade: Any,
    diagnostic: Any,
    student_name: str = "",
    remediation_subject: Any = None,
    rubric: Any = None,
) -> None:
    """Genere le rapport PDF via xhtml2pdf (HTML+CSS -> PDF)."""
    try:
        from xhtml2pdf import pisa
    except ImportError:
        raise RuntimeError(
            "xhtml2pdf non installe. Lancez : pip install xhtml2pdf>=0.2.14"
        )
    from jinja2 import Environment, FileSystemLoader

    font_name = _register_unicode_font()

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("rapport_correction.html.j2")
    ctx = _build_context(copy_id, grade, diagnostic, student_name, rubric)
    ctx["FONT_NAME"] = font_name
    html_content = template.render(**ctx)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as pdf_file:
        result = pisa.CreatePDF(html_content, dest=pdf_file, encoding="utf-8")

    if result.err:
        raise RuntimeError(
            f"xhtml2pdf : {result.err} erreur(s) lors de la generation de {output_path.name}"
        )
    logger.info("[%s] Rapport PDF genere -> %s", copy_id, output_path)
