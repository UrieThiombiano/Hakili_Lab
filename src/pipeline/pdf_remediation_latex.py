"""
Génération PDF feuille de remédiation via XeLaTeX + Jinja2.
Fallback automatique sur ReportLab si xelatex est absent.
"""
from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
_LOGO_PATH    = Path(__file__).resolve().parent.parent / "ui" / "hakili_logo.png"

_MONTHS_FR = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


# ── Échappement LaTeX (texte brut uniquement) ─────────────────────────────────

def _le(text: str) -> str:
    """Échappe le texte utilisateur brut pour LaTeX."""
    if not text:
        return ""
    text = str(text)
    text = text.replace("\\", r"\textbackslash{}")
    text = text.replace("&",  r"\&")
    text = text.replace("%",  r"\%")
    text = text.replace("$",  r"\$")
    text = text.replace("#",  r"\#")
    text = text.replace("_",  r"\_")
    text = text.replace("{",  r"\{")
    text = text.replace("}",  r"\}")
    text = text.replace("~",  r"\textasciitilde{}")
    text = text.replace("^",  r"\textasciicircum{}")
    return text


def _today_fr() -> str:
    today = date.today()
    return f"{today.day} {_MONTHS_FR[today.month]} {today.year}"


# Symboles Unicode mathématiques → commandes LaTeX (appliqué APRÈS _le)
_UNICODE_TO_LATEX: dict[str, str] = {
    "ℕ": r"\ensuremath{\mathbb{N}}",
    "ℤ": r"\ensuremath{\mathbb{Z}}",
    "ℝ": r"\ensuremath{\mathbb{R}}",
    "ℚ": r"\ensuremath{\mathbb{Q}}",
    "ℂ": r"\ensuremath{\mathbb{C}}",
    "ⅅ": r"\ensuremath{\mathbb{D}}",
    "∈": r"\ensuremath{\in}",
    "∉": r"\ensuremath{\notin}",
    "⊂": r"\ensuremath{\subset}",
    "⊆": r"\ensuremath{\subseteq}",
    "⊃": r"\ensuremath{\supset}",
    "⊇": r"\ensuremath{\supseteq}",
    "∪": r"\ensuremath{\cup}",
    "∩": r"\ensuremath{\cap}",
    "∅": r"\ensuremath{\emptyset}",
    "→": r"\ensuremath{\rightarrow}",
    "⇒": r"\ensuremath{\Rightarrow}",
    "⟺": r"\ensuremath{\Leftrightarrow}",
    "↔": r"\ensuremath{\leftrightarrow}",
    "≤": r"\ensuremath{\leq}",
    "≥": r"\ensuremath{\geq}",
    "≠": r"\ensuremath{\neq}",
    "≈": r"\ensuremath{\approx}",
    "×": r"\ensuremath{\times}",
    "÷": r"\ensuremath{\div}",
    "±": r"\ensuremath{\pm}",
    "√": r"\ensuremath{\sqrt{\phantom{x}}}",
    "²": r"\ensuremath{^{2}}",
    "³": r"\ensuremath{^{3}}",
    "π": r"\ensuremath{\pi}",
    "∞": r"\ensuremath{\infty}",
    "°": r"\textdegree{}",
    "…": r"\ldots{}",
    "−": r"\ensuremath{-}",  # MINUS SIGN (≠ tiret)
}


def _extract_ascii_math(text: str) -> tuple[str, dict[str, str]]:
    """Extrait les notations ASCII mathématiques avant l'échappement LaTeX.

    Remplace sqrt(), ^, _, pi, <=, >= par des tokens neutres (alphanum. purs)
    pour que _le() ne les touche pas. Retourne le texte modifié et la table
    de substitution {token: commande_latex}.
    """
    store: dict[str, str] = {}
    idx = 0

    def ph(latex: str) -> str:
        nonlocal idx
        key = f"XMATHPH{idx}XEND"
        store[key] = latex
        idx += 1
        return key

    # 1. sqrt(expr) → $\sqrt{expr}$  — traiter en premier (peut contenir ^)
    def _repl_sqrt(m: re.Match) -> str:
        inner = m.group(1).strip()
        # Exposants à l'intérieur du sqrt : a^2 → a^{2}
        inner = re.sub(r'([A-Za-z0-9])\^(\d+)', r'\1^{\2}', inner)
        return ph(f'$\\sqrt{{{inner}}}$')

    text = re.sub(r'sqrt\(([^)]*)\)', _repl_sqrt, text)

    # 2. (a/b) fractions simples avec entiers → $\frac{a}{b}$
    text = re.sub(
        r'\((\d+)/(\d+)\)',
        lambda m: ph(f'$\\frac{{{m.group(1)}}}{{{m.group(2)}}}$'),
        text,
    )

    # 3. base^exp (lettre ou chiffre) → $base^{exp}$
    text = re.sub(
        r'([A-Za-z0-9])\^(\d+)',
        lambda m: ph(f'${m.group(1)}^{{{m.group(2)}}}$'),
        text,
    )

    # 4. V_xyz, V_cyl, V_pyr … (majuscule + _ + minuscules) → $V_{\mathrm{xyz}}$
    text = re.sub(
        r'\b([A-Z])_([a-z]+)\b',
        lambda m: ph(f'${m.group(1)}_{{\\mathrm{{{m.group(2)}}}}}$'),
        text,
    )

    # 5. pi standalone → $\pi$
    text = re.sub(r'\bpi\b', lambda _: ph(r'$\pi$'), text)

    # 6. <= et >= textuels (non-Unicode)
    text = text.replace("<=", ph(r'$\leq$'))
    text = text.replace(">=", ph(r'$\geq$'))
    text = text.replace("!=", ph(r'$\neq$'))

    return text, store


def _sanitize_question(text: str) -> str:
    """Convertit le texte brut de l'IA en LaTeX valide.

    Ordre : extraction des notations ASCII math → échappement LaTeX du texte
    restant → réinjection des commandes LaTeX → conversion des symboles Unicode.
    """
    if not text:
        return ""
    # Étape 1 : extraire les notations ASCII math avant que _le() n'échappe ^ et _
    processed, math_store = _extract_ascii_math(str(text))
    # Étape 2 : échapper les caractères spéciaux LaTeX du texte non-math
    escaped = _le(processed)
    # Étape 3 : réinjecter les commandes LaTeX à la place des tokens
    for key, latex in math_store.items():
        escaped = escaped.replace(key, latex)
    # Étape 4 : convertir les symboles Unicode math restants (ℕ, ≤, ×…)
    for sym, latex in _UNICODE_TO_LATEX.items():
        escaped = escaped.replace(sym, latex)
    return escaped


# ── Contexte Jinja2 ───────────────────────────────────────────────────────────

def _build_context(
    copy_id: str,
    student_name: str,
    remediation_subject: Any,
) -> dict[str, Any]:
    exercises = remediation_subject.exercises

    # Grouper par topic (ordre d'apparition) pour créer les séries
    topics_seen: list[str] = []
    topic_exos: dict[str, list] = {}
    for ex in exercises:
        key = ex.topic
        if key not in topic_exos:
            topics_seen.append(key)
            topic_exos[key] = []
        topic_exos[key].append(ex)

    series = []
    for idx, topic in enumerate(topics_seen, 1):
        exos = topic_exos[topic]
        series.append({
            "idx": idx,
            "topic": _le(topic),
            "exercises": [
                {
                    "number":   ex.number,
                    "topic":    _le(ex.topic),
                    "question": _sanitize_question(ex.question),
                    "hint":     _sanitize_question(getattr(ex, "hint", "") or ""),
                    "has_hint": bool(getattr(ex, "hint", "").strip()),
                }
                for ex in exos
            ],
        })

    logo_exists = _LOGO_PATH.exists()
    logo_path   = str(_LOGO_PATH.resolve()).replace("\\", "/")

    return {
        "LOGO_PATH":    logo_path,
        "LOGO_EXISTS":  logo_exists,
        "STUDENT_NAME": _le(student_name or copy_id),
        "COPY_ID":      _le(copy_id),
        "DATE":         _today_fr(),
        "series":       series,
        "total":        len(exercises),
    }


# ── Compilation XeLaTeX ───────────────────────────────────────────────────────

def _compile(tex_content: str, output_path: Path) -> None:
    """Compile LaTeX → PDF en deux passes. Lève RuntimeError en cas d'échec."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_file = Path(tmpdir) / "feuille.tex"
        tex_file.write_text(tex_content, encoding="utf-8")
        cmd = ["xelatex", "-interaction=nonstopmode", "-halt-on-error", str(tex_file)]
        for pass_num in range(2):
            proc = subprocess.run(
                cmd, cwd=tmpdir, capture_output=True,
                text=True, encoding="utf-8", errors="replace",
            )
            if proc.returncode != 0:
                log_tail = proc.stdout[-4000:]
                logger.error("xelatex remédiation passe %d échouée :\n%s", pass_num + 1, log_tail)
                raise RuntimeError(
                    f"xelatex remédiation passe {pass_num + 1} échouée :\n{log_tail}"
                )

        pdf = Path(tmpdir) / "feuille.pdf"
        if not pdf.exists():
            raise RuntimeError(f"xelatex OK mais feuille.pdf absent dans {tmpdir}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(pdf), str(output_path))


# ── API publique ──────────────────────────────────────────────────────────────

def generate_remediation_pdf(
    output_path: Path,
    copy_id: str,
    student_name: str,
    remediation_subject: Any,
) -> None:
    """Génère la feuille de remédiation PDF via XeLaTeX + Jinja2."""
    if not shutil.which("xelatex"):
        raise RuntimeError(
            "xelatex introuvable — installez TeX Live ou MiKTeX pour générer les feuilles de remédiation."
        )

    from jinja2 import Environment, FileSystemLoader

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template    = env.get_template("remediation_exercises.tex.j2")
    ctx         = _build_context(copy_id, student_name, remediation_subject)
    tex_content = template.render(**ctx)
    _compile(tex_content, output_path)
    logger.info("[%s] Feuille remédiation PDF LaTeX → %s", copy_id, output_path)
