"""
Génération du rapport PDF — éléments D-CEO-06 :
  1. Note totale + détail par question
  2. Commentaire pédagogique par question
  3. Zones marquées "Révision requise"
  4. Diagnostic des compétences
  5. Plan de remédiation élève
  6. Score de confiance IA
  7. Logo Hakili Lab + nom de l'élève
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from src.models.domain import CopyGrade, DiagnosticResult, QualityReport, RemediationSubject

_PRIMARY    = colors.HexColor("#001F5C")
_LIGHT_BLUE = colors.HexColor("#4A90E2")
_WARN       = colors.HexColor("#E67E22")
_GRAY       = colors.HexColor("#7F8C8D")
_LIGHT_GRAY = colors.HexColor("#ECF0F1")
_GREEN      = colors.HexColor("#27AE60")
_RED        = colors.HexColor("#E74C3C")

_LOGO_PATH = Path(__file__).parent.parent / "ui" / "hakili_logo.png"

W, H   = A4
MARGIN = 20 * mm
_CW    = W - 2 * MARGIN   # largeur utile du contenu


# ── Helpers ────────────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """Échappe les caractères XML spéciaux avant injection dans un Paragraph."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    """Crée un Paragraph pour les cellules de tableau — garantit le retour à la ligne."""
    return Paragraph(text, style)


def _alt_rows(n_data_rows: int) -> list[tuple]:
    """Génère les commandes BACKGROUND pour les lignes alternées (commence à la ligne 1)."""
    cmds = []
    for i in range(1, n_data_rows + 1):
        if i % 2 == 0:
            cmds.append(("BACKGROUND", (0, i), (-1, i), _LIGHT_GRAY))
    return cmds


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title":     ParagraphStyle("title",     parent=base["Heading1"], textColor=_PRIMARY,     fontSize=16, spaceAfter=4),
        "h2":        ParagraphStyle("h2",         parent=base["Heading2"], textColor=_PRIMARY,     fontSize=12, spaceAfter=2),
        "h3":        ParagraphStyle("h3",         parent=base["Heading3"], textColor=_LIGHT_BLUE,  fontSize=10, spaceAfter=2),
        "body":      ParagraphStyle("body",       parent=base["Normal"],   fontSize=9,  leading=13),
        "warn":      ParagraphStyle("warn",       parent=base["Normal"],   fontSize=9,  textColor=_WARN),
        "small":     ParagraphStyle("small",      parent=base["Normal"],   fontSize=8,  textColor=_GRAY),
        "cell":      ParagraphStyle("cell",       parent=base["Normal"],   fontSize=8,  leading=11),
        "cell_hdr":  ParagraphStyle("cell_hdr",   parent=base["Normal"],   fontSize=8,  leading=11, fontName="Helvetica-Bold", textColor=colors.white),
    }


def _header_footer(canvas, doc) -> None:  # noqa: ANN001
    canvas.saveState()
    if _LOGO_PATH.exists():
        canvas.drawImage(
            str(_LOGO_PATH), MARGIN, H - 18 * mm,
            width=12 * mm, height=12 * mm, preserveAspectRatio=True, mask="auto",
        )
    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(_PRIMARY)
    canvas.drawString(MARGIN + 14 * mm, H - 12 * mm, "HAKILI LAB — Rapport de correction IA")
    canvas.setStrokeColor(_LIGHT_BLUE)
    canvas.setLineWidth(1)
    canvas.line(MARGIN, H - 20 * mm, W - MARGIN, H - 20 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(_GRAY)
    canvas.drawCentredString(
        W / 2, 10 * mm,
        f"Page {doc.page} — Document confidentiel — Usage pédagogique exclusif",
    )
    canvas.restoreState()


# ── Point d'entrée ─────────────────────────────────────────────────────────────

def generate_copy_report(
    output_path: Path,
    copy_id: str,
    grade: CopyGrade,
    diagnostic: DiagnosticResult | None,
    quality: QualityReport,
    student_name: str = "",
    remediation_subject: RemediationSubject | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    S = _styles()

    doc = BaseDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=25 * mm,
        bottomMargin=18 * mm,
    )
    frame = Frame(MARGIN, 18 * mm, _CW, H - 43 * mm, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_header_footer)])

    story: list = []

    # ── En-tête copie ──────────────────────────────────────────────────────────
    display_name = _esc(student_name) if student_name else _esc(copy_id)
    story.append(Paragraph(f"Élève : <b>{display_name}</b>", S["title"]))
    story.append(HRFlowable(width="100%", thickness=2, color=_LIGHT_BLUE, spaceAfter=6))

    # ── 1 & 6 — Note totale + confiance IA ────────────────────────────────────
    avg_conf = (
        sum(q.confidence for q in grade.questions) / len(grade.questions)
        if grade.questions else 0.0
    )

    summary_data = [
        [
            _p("Note totale", S["cell"]),
            _p(f"<font size='14' color='#001F5C'><b>{grade.total_score} / {grade.total_possible}</b></font>", S["cell"]),
        ],
        [
            _p("Confiance IA moyenne", S["cell"]),
            _p(f"{avg_conf:.0%}", S["cell"]),
        ],
        [
            _p("Instructions expert utilisées", S["cell"]),
            _p("Oui" if grade.expert_instructions_used else "Non", S["cell"]),
        ],
    ]
    if quality.global_quality == "poor":
        summary_data.append([
            _p("Qualité image", S["cell"]),
            _p('<font color="#E67E22"><b>Insuffisante — rescan recommandé</b></font>', S["cell"]),
        ])

    summary_table = Table(summary_data, colWidths=[60 * mm, 90 * mm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, -1), _LIGHT_GRAY),
        ("TEXTCOLOR",     (0, 0), (0, -1), _PRIMARY),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        *_alt_rows(len(summary_data) - 1),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 6 * mm))

    # ── 2 & 3 — Détail par question ────────────────────────────────────────────
    story.append(Paragraph("Détail de la correction", S["h2"]))

    col_q  = 20 * mm
    col_sc = 16 * mm
    col_cf = 18 * mm
    col_cm = _CW - col_q - col_sc - col_cf   # reste pour le commentaire

    q_data: list[list] = [[
        _p("Question",   S["cell_hdr"]),
        _p("Score",      S["cell_hdr"]),
        _p("Confiance",  S["cell_hdr"]),
        _p("Commentaire", S["cell_hdr"]),
    ]]

    review_items = []
    for q in grade.questions:
        if q.score == 1:
            score_html = '<font color="#27AE60"><b>OK  1</b></font>'
        else:
            score_html = '<font color="#E74C3C"><b>X  0</b></font>'

        q_data.append([
            _p(_esc(q.rubric_item_id), S["cell"]),
            _p(score_html, S["cell"]),
            _p(f"{q.confidence:.0%}", S["cell"]),
            _p(_esc(q.comment), S["cell"]),
        ])
        if q.requires_review:
            review_items.append(q)

    q_table = Table(q_data, colWidths=[col_q, col_sc, col_cf, col_cm])
    q_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), _PRIMARY),
        ("ALIGN",         (1, 0), (2, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#BDC3C7")),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        *_alt_rows(len(q_data) - 1),
    ]))
    story.append(q_table)
    story.append(Spacer(1, 4 * mm))

    # ── 3 — Révision manuelle requise ─────────────────────────────────────────
    if review_items:
        story.append(Paragraph(
            '<font color="#E67E22"><b>Révision manuelle requise</b></font>',
            S["h2"],
        ))
        for q in review_items:
            story.append(Paragraph(
                f"<b>{_esc(q.rubric_item_id)}</b> — Réponse observée : <i>{_esc(q.observed_answer)}</i>",
                S["warn"],
            ))
        story.append(Spacer(1, 4 * mm))

    # ── 4 — Diagnostic des compétences ────────────────────────────────────────
    if diagnostic:
        story.append(HRFlowable(width="100%", thickness=1, color=_LIGHT_GRAY, spaceAfter=4))
        story.append(Paragraph("Diagnostic des compétences", S["h2"]))

        if diagnostic.strengths:
            story.append(Paragraph("Points forts", S["h3"]))
            for s in diagnostic.strengths:
                story.append(Paragraph(f"• {_esc(s)}", S["body"]))
            story.append(Spacer(1, 2 * mm))

        if diagnostic.weaknesses:
            story.append(Paragraph("Points à renforcer", S["h3"]))
            for w in diagnostic.weaknesses:
                story.append(Paragraph(f"• {_esc(w)}", S["body"]))
            story.append(Spacer(1, 2 * mm))

        if diagnostic.skills:
            story.append(Paragraph("Évaluation par compétence", S["h3"]))

            col_sk  = 55 * mm
            col_lv  = 22 * mm
            col_obs = _CW - col_sk - col_lv

            skill_data: list[list] = [[
                _p("Compétence",  S["cell_hdr"]),
                _p("Niveau",      S["cell_hdr"]),
                _p("Observation", S["cell_hdr"]),
            ]]

            level_html = {
                "mastered": '<font color="#27AE60"><b>Acquis</b></font>',
                "partial":  '<font color="#E67E22">Partiel</font>',
                "weak":     '<font color="#E74C3C">Fragile</font>',
                "unknown":  "Inconnu",
            }
            for sk in diagnostic.skills:
                skill_data.append([
                    _p(_esc(sk.name), S["cell"]),
                    _p(level_html.get(sk.level, _esc(sk.level)), S["cell"]),
                    _p(_esc(sk.evidence), S["cell"]),
                ])

            sk_table = Table(skill_data, colWidths=[col_sk, col_lv, col_obs])
            sk_table.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, 0), _PRIMARY),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#BDC3C7")),
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING",   (0, 0), (-1, -1), 5),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
                *_alt_rows(len(skill_data) - 1),
            ]))
            story.append(sk_table)
            story.append(Spacer(1, 4 * mm))

        # ── Causes profondes ───────────────────────────────────────────────────
        if diagnostic.root_causes:
            story.append(HRFlowable(width="100%", thickness=1, color=_LIGHT_GRAY, spaceAfter=4))
            story.append(Paragraph("Analyse des erreurs cachées", S["h2"]))
            story.append(Paragraph(
                "Ces erreurs profondes sont la vraie cause des points perdus — "
                "corriger ces mécanismes corrigera plusieurs questions à la fois.",
                S["small"],
            ))
            story.append(Spacer(1, 3 * mm))

            rc_data: list[list] = [[
                _p("Erreur visible",  S["cell_hdr"]),
                _p("Cause cachée",    S["cell_hdr"]),
                _p("Questions",       S["cell_hdr"]),
            ]]
            col_vis = 45 * mm
            col_cau = _CW - col_vis - 25 * mm
            col_qs  = 25 * mm

            for rc in diagnostic.root_causes:
                qs = ", ".join(rc.linked_questions) if rc.linked_questions else "—"
                rc_data.append([
                    _p(_esc(rc.visible_error),  S["cell"]),
                    _p(_esc(rc.hidden_cause),    S["cell"]),
                    _p(_esc(qs),                 S["cell"]),
                ])

            rc_table = Table(rc_data, colWidths=[col_vis, col_cau, col_qs])
            rc_table.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, 0), _WARN),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#BDC3C7")),
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING",   (0, 0), (-1, -1), 5),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
                *_alt_rows(len(rc_data) - 1),
            ]))
            story.append(rc_table)
            story.append(Spacer(1, 4 * mm))

        # ── 5 — Plan de remédiation ────────────────────────────────────────────
        if diagnostic.remediation_plan:
            story.append(Paragraph("Plan de remédiation personnalisé", S["h2"]))
            for item in sorted(diagnostic.remediation_plan, key=lambda x: x.priority):
                story.append(Paragraph(
                    f"<b>{item.priority}. {_esc(item.topic)}</b> — {_esc(item.action)}",
                    S["body"],
                ))
                story.append(Spacer(1, 1 * mm))
            story.append(Spacer(1, 4 * mm))

    doc.build(story)


# ── PDF Sujet de remédiation (document élève) ─────────────────────────────────

def generate_remediation_pdf(
    output_path: Path,
    copy_id: str,
    student_name: str,
    remediation_subject: RemediationSubject,
) -> None:
    """
    Génère un sujet de remédiation autonome — destiné à l'élève.
    Format feuille d'exercices : pas de scores, pas de diagnostic visible.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    S = _styles()

    doc = BaseDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=25 * mm,
        bottomMargin=18 * mm,
    )
    frame = Frame(MARGIN, 18 * mm, _CW, H - 43 * mm, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_header_footer)])

    story: list = []

    # ── En-tête ────────────────────────────────────────────────────────────────
    display_name = _esc(student_name) if student_name else _esc(copy_id)
    story.append(Paragraph("Sujet de remédiation personnalisé", S["title"]))
    story.append(HRFlowable(width="100%", thickness=2, color=_LIGHT_BLUE, spaceAfter=6))

    # Tableau identité élève
    identity_data = [
        [_p("Élève", S["cell"]),      _p(f"<b>{display_name}</b>", S["cell"])],
        [_p("Établissement", S["cell"]), _p("", S["cell"])],
        [_p("Date", S["cell"]),       _p("", S["cell"])],
    ]
    id_table = Table(identity_data, colWidths=[40 * mm, 110 * mm])
    id_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, -1), _LIGHT_GRAY),
        ("TEXTCOLOR",     (0, 0), (0, -1), _PRIMARY),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    story.append(id_table)
    story.append(Spacer(1, 6 * mm))

    # Consigne générale
    story.append(Paragraph(
        "Ces exercices ont été conçus spécialement pour toi. "
        "Travaille-les dans l'ordre — chaque série consolide un mécanisme précis. "
        "Lis bien l'aide avant de commencer chaque exercice.",
        S["body"],
    ))
    story.append(Spacer(1, 8 * mm))

    # ── Séries d'exercices ────────────────────────────────────────────────────
    current_topic = None
    serie_num = 0
    for ex in remediation_subject.exercises:
        if ex.topic != current_topic:
            current_topic = ex.topic
            serie_num += 1
            if serie_num > 1:
                story.append(Spacer(1, 4 * mm))
            story.append(HRFlowable(width="100%", thickness=1, color=_LIGHT_GRAY, spaceAfter=3))
            story.append(Paragraph(
                f"Série {serie_num} — {_esc(ex.topic)}",
                S["h2"],
            ))
            story.append(Spacer(1, 2 * mm))

        story.append(Paragraph(
            f"<b>Exercice {ex.number}.</b>  {_esc(ex.question)}",
            S["body"],
        ))
        if ex.hint:
            story.append(Paragraph(
                f"<i>Aide :</i> {_esc(ex.hint)}",
                S["small"],
            ))
        story.append(Spacer(1, 5 * mm))

    # ── Pied ──────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=_LIGHT_GRAY, spaceAfter=3))
    story.append(Paragraph(
        "Hakili Lab · Sujet de remédiation personnalisé — Usage pédagogique exclusif.",
        S["small"],
    ))

    doc.build(story)
