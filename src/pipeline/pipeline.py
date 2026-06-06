"""
Pipeline principal — Hakili Lab.

Flux : ingestion → qualité → transcription → [orchestrateur] → correction
     → [orchestrateur] → diagnostic → [orchestrateur] → remédiation
     → [orchestrateur] → export PDF + JSON

Routage multi-providers (auto selon clés .env) :
  Transcription  → Gemini 2.0 Flash (si GOOGLE_API_KEY)  sinon Claude Sonnet
  Correction     → DeepSeek V3      (si DEEPSEEK_API_KEY) sinon Claude Sonnet
  Diagnostic     → DeepSeek R1      (si DEEPSEEK_API_KEY) sinon Claude Sonnet
  Remédiation    → Mistral Small    (si MISTRAL_API_KEY)  sinon Claude Sonnet
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from src.api.claude_client import ClaudeClient
from src.core.config import settings
from src.models.domain import (
    CopyGrade,
    DiagnosticResult,
    IngestionResult,
    QualityReport,
    QuestionGrade,
    Rubric,
    RemediationSubject,
    TranscriptionResult,
)
from src.pipeline.image_quality import assess_copy_quality
from src.pipeline.ingestion import ingest_images, ingest_pdf
from src.pipeline.orchestrator import (
    ValidationIssue,
    validate_diagnostic,
    validate_grading,
    validate_remediation,
    validate_transcription,
)
from src.pipeline.pdf_report import generate_copy_report, generate_remediation_pdf

logger = logging.getLogger(__name__)


# ── Ensemble voting pour le grading ──────────────────────────────────────────
#
# Principe : lancer la correction N fois avec temperature > 0 pour obtenir des
# échantillons diversifiés, puis fusionner par vote majoritaire question par
# question. Les questions en désaccord sont automatiquement flaggées
# requires_review=True — c'est le signal d'incertitude réelle, pas du bruit.

_ENSEMBLE_RUNS: int = 3
_ENSEMBLE_TEMPERATURE: float = 0.4   # diversité suffisante sans dégradation de qualité


def _grade_ensemble(
    grading_client,
    fallback_client: ClaudeClient,
    *,
    copy_id: str,
    transcription: TranscriptionResult,
    rubric: Rubric,
    subject_text: str,
    expert_instructions: str,
) -> CopyGrade | None:
    """
    Lance le grading _ENSEMBLE_RUNS fois, fusionne par vote majoritaire.

    - Score final d'une question = score obtenu par la majorité des runs.
    - requires_review=True si au moins 1 run est en désaccord avec la majorité.
    - confidence réduite à ≤ 0.6 en cas de désaccord.
    """
    grades: list[CopyGrade] = []

    for run_idx in range(_ENSEMBLE_RUNS):
        resp = grading_client.grade(
            transcription=transcription,
            rubric=rubric,
            subject_text=subject_text,
            expert_instructions=expert_instructions,
            temperature=_ENSEMBLE_TEMPERATURE,
        )
        if not resp.success or resp.data is None:
            if type(grading_client).__name__ != "ClaudeClient":
                resp = fallback_client.grade(
                    transcription=transcription,
                    rubric=rubric,
                    subject_text=subject_text,
                    expert_instructions=expert_instructions,
                    temperature=_ENSEMBLE_TEMPERATURE,
                )
        if resp.success and resp.data is not None:
            resp.data.copy_id = copy_id
            grades.append(resp.data)
            logger.info("[%s] Run ensemble %d/%d → %d questions", copy_id, run_idx + 1, _ENSEMBLE_RUNS, len(resp.data.questions))

    if not grades:
        return None

    if len(grades) == 1:
        logger.warning("[%s] Ensemble : un seul run réussi — résultat non consolidé.", copy_id)
        return grades[0]

    # ── Fusion par vote majoritaire ────────────────────────────────────────────
    # Collecte tous les identifiants de questions vus dans l'ensemble des runs
    ordered_ids: list[str] = []
    seen_ids: set[str] = set()
    for g in grades:
        for q in g.questions:
            if q.rubric_item_id not in seen_ids:
                ordered_ids.append(q.rubric_item_id)
                seen_ids.add(q.rubric_item_id)

    merged_questions: list[QuestionGrade] = []
    disagreements: list[str] = []

    for qid in ordered_ids:
        # Collecte les réponses de chaque run pour cette question
        run_answers: list[tuple[int, float, str, str]] = []  # score, conf, comment, observed
        for g in grades:
            for q in g.questions:
                if q.rubric_item_id == qid:
                    run_answers.append((q.score, q.confidence, q.comment, q.observed_answer))
                    break

        if not run_answers:
            continue

        scores = [a[0] for a in run_answers]
        score_counts = Counter(scores)
        majority_score = score_counts.most_common(1)[0][0]
        agreement = score_counts[majority_score] / len(scores)
        is_disagreement = agreement < 1.0

        if is_disagreement:
            disagreements.append(qid)

        # Prend le commentaire/réponse d'un run qui a voté pour le score majoritaire
        majority_answer = next(
            (a for a in run_answers if a[0] == majority_score), run_answers[0]
        )
        avg_confidence = sum(a[1] for a in run_answers) / len(run_answers)
        final_confidence = min(avg_confidence, 0.6) if is_disagreement else avg_confidence

        merged_questions.append(QuestionGrade(
            rubric_item_id=qid,
            score=majority_score,
            confidence=final_confidence,
            comment=majority_answer[2],
            observed_answer=majority_answer[3],
            requires_review=is_disagreement,
        ))

    total_score = sum(q.score for q in merged_questions)
    total_possible = len(merged_questions)

    if disagreements:
        logger.warning(
            "[%s] Ensemble — %d question(s) en désaccord (flaggées requires_review) : %s",
            copy_id, len(disagreements), ", ".join(disagreements),
        )

    logger.warning(
        "[%s] Ensemble fusionné — %d/%d pts | %d questions | %d désaccords",
        copy_id, total_score, total_possible, len(merged_questions), len(disagreements),
    )

    return CopyGrade(
        copy_id=copy_id,
        total_score=total_score,
        total_possible=total_possible,
        questions=merged_questions,
    )


# ── Factories de clients (import lazy pour éviter les erreurs au démarrage) ───

def _make_transcription_client():
    """Gemini Flash si GOOGLE_API_KEY + VISION_PROVIDER=gemini, sinon Claude."""
    if settings.vision_provider.lower() == "gemini" and settings.google_api_key:
        from src.api.gemini_client import GeminiTranscriptionClient
        return GeminiTranscriptionClient()
    return ClaudeClient()


def _make_grading_client():
    """DeepSeek V3 si DEEPSEEK_API_KEY disponible, sinon Claude Sonnet."""
    if settings.deepseek_api_key:
        from src.api.deepseek_client import DeepSeekClient
        return DeepSeekClient()
    return ClaudeClient()


def _make_diagnostic_client():
    """DeepSeek R1 si DEEPSEEK_API_KEY disponible, sinon Claude Haiku."""
    if settings.deepseek_api_key:
        from src.api.deepseek_client import DeepSeekClient
        return DeepSeekClient()
    return ClaudeClient()


def _make_remediation_client():
    """Mistral Small si MISTRAL_API_KEY disponible, sinon Claude Sonnet."""
    if settings.mistral_api_key:
        from src.api.mistral_client import MistralRemediationClient
        return MistralRemediationClient()
    return ClaudeClient()


# ── Résultat du pipeline ──────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    copy_id: str
    student_name: str
    ingestion: IngestionResult
    quality: QualityReport
    transcription: TranscriptionResult | None = None
    grade: CopyGrade | None = None
    diagnostic: DiagnosticResult | None = None
    remediation_subject: RemediationSubject | None = None
    pdf_path: Path | None = None
    remediation_pdf_path: Path | None = None
    json_path: Path | None = None
    errors: list[str] = field(default_factory=list)
    # Problèmes détectés par l'orchestrateur, affichés dans l'interface enseignant
    validation_issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.grade is not None and not self.errors


# ── Pipeline principal ────────────────────────────────────────────────────────

def run_single_copy(
    *,
    copy_id: str,
    student_name: str = "",
    file_paths: list[Path],
    rubric: Rubric,
    rubric_file_path: Path | None = None,
    subject_text: str = "",
    subject_file_path: Path | None = None,
    expert_instructions: str = "",
    runs_dir: Path | None = None,
) -> PipelineResult:
    out = Path(runs_dir or settings.runs_dir)

    # Clients spécialisés — initialisés une seule fois par run
    claude_client = ClaudeClient()           # Extraction barème/énoncé (vision + fallback)
    transcription_client = _make_transcription_client()
    grading_client = _make_grading_client()
    diagnostic_client = _make_diagnostic_client()
    remediation_client = _make_remediation_client()

    logger.warning(
        "[%s] MODÈLES — transcription=%s | grading=%s | diagnostic=%s | remédiation=%s",
        copy_id,
        type(transcription_client).__name__,
        type(grading_client).__name__,
        type(diagnostic_client).__name__,
        type(remediation_client).__name__,
    )

    # ── Extraction énoncé (vision) ────────────────────────────────────────────
    if not subject_text.strip() and subject_file_path is not None:
        logger.info("[%s] Extraction texte énoncé…", copy_id)
        subject_text = claude_client.extract_subject(subject_file_path)

    # ── Extraction barème depuis fichier PDF/image ────────────────────────────
    if not rubric.items and rubric_file_path is not None:
        logger.info("[%s] Extraction du barème depuis fichier…", copy_id)
        rubric_resp = claude_client.extract_rubric(rubric_file_path)
        if rubric_resp.success and rubric_resp.data is not None:
            rubric = rubric_resp.data
            logger.info("[%s] Barème extrait : %d items.", copy_id, len(rubric.items))
        else:
            logger.warning("[%s] Extraction barème échouée : %s", copy_id, rubric_resp.error)

    # 1. Ingestion ──────────────────────────────────────────────────────────────
    logger.info("[%s] Ingestion (%d fichier(s))…", copy_id, len(file_paths))
    if len(file_paths) == 1 and file_paths[0].suffix.lower() == ".pdf":
        ingestion = ingest_pdf(file_paths[0], copy_id, out)
    else:
        ingestion = ingest_images(file_paths, copy_id, out)

    # Extraction du nom de l'élève depuis la première page si non fourni
    # ou si le nom ressemble à un nom de fichier (chiffres seuls, 1-2 caractères)
    _name_is_placeholder = (
        not student_name.strip()
        or student_name.strip().replace(" ", "").isdigit()
        or len(student_name.strip()) <= 2
    )
    if _name_is_placeholder and ingestion.pages:
        logger.info("[%s] Extraction du nom de l'élève depuis la première page…", copy_id)
        extracted = claude_client.extract_student_name(ingestion.pages[0])
        if extracted:
            student_name = extracted
            logger.info("[%s] Nom extrait : %s", copy_id, student_name)

    result = PipelineResult(
        copy_id=copy_id,
        student_name=student_name,
        ingestion=ingestion,
        quality=QualityReport(copy_id=copy_id, global_quality="good", pages=[], rescan_requested=False),
    )

    # 2. Qualité image ──────────────────────────────────────────────────────────
    logger.info("[%s] Contrôle qualité (%d pages)…", copy_id, ingestion.total_pages)
    result.quality = assess_copy_quality(copy_id, ingestion.pages)

    if result.quality.global_quality == "poor":
        logger.warning("[%s] Qualité insuffisante — traitement poursuivi avec avertissement.", copy_id)

    # 3. Transcription ──────────────────────────────────────────────────────────
    logger.info("[%s] Transcription (%s)…", copy_id, type(transcription_client).__name__)
    transcription_resp = transcription_client.transcribe(copy_id, ingestion.pages)

    # Fallback Claude si le provider principal échoue (ex: Gemini 429 quota)
    if not transcription_resp.success or transcription_resp.data is None:
        primary_name = type(transcription_client).__name__
        if primary_name != "ClaudeClient":
            logger.warning(
                "[%s] %s échoué — fallback transcription → %s",
                copy_id, primary_name, settings.claude_model_heavy,
            )
            transcription_resp = claude_client.transcribe(copy_id, ingestion.pages)

    if not transcription_resp.success or transcription_resp.data is None:
        result.errors.append(f"Transcription échouée : {transcription_resp.error}")
        return result

    # ── Orchestrateur ① : validation transcription ────────────────────────────
    vt = validate_transcription(transcription_resp.data)
    result.validation_issues.extend(vt.issues)
    if not vt.valid:
        result.errors.append(f"Transcription invalide : {vt.summary}")
        return result
    result.transcription = vt.data

    # 4. Extraction des questions si pas de barème → barème virtuel stable
    #    (temperature=0 : lecture factuelle, une seule fois)
    if not rubric.items:
        logger.info("[%s] Aucun barème fourni — extraction des questions depuis la transcription…", copy_id)
        rubric = claude_client.extract_questions_from_transcription(result.transcription)
        if not rubric.items:
            logger.warning(
                "[%s] Extraction échouée — la correction s'appuiera sur l'auto-détection.",
                copy_id,
            )

    # 5. Correction par ensemble voting ────────────────────────────────────────
    #    Chaque run utilise temperature=0.4 pour la diversité ; la fusion par
    #    vote majoritaire donne un résultat plus robuste qu'un seul run.
    logger.info("[%s] Correction ensemble (%d runs, %s)…", copy_id, _ENSEMBLE_RUNS, type(grading_client).__name__)
    merged_grade = _grade_ensemble(
        grading_client,
        claude_client,
        copy_id=copy_id,
        transcription=result.transcription,
        rubric=rubric,
        subject_text=subject_text,
        expert_instructions=expert_instructions,
    )
    if merged_grade is None:
        result.errors.append("Correction échouée : tous les runs ont échoué.")
        return result

    # ── Orchestrateur ② : validation correction ───────────────────────────────
    rubric_provided = bool(rubric.items)
    vg = validate_grading(merged_grade, rubric_provided=rubric_provided)
    result.validation_issues.extend(vg.issues)
    if not vg.valid:
        result.errors.append(f"Correction invalide : {vg.summary}")
        return result
    result.grade = vg.data

    # 6. Diagnostic ─────────────────────────────────────────────────────────────
    logger.info("[%s] Diagnostic (%s)…", copy_id, type(diagnostic_client).__name__)
    diag_resp = diagnostic_client.diagnose(result.grade)
    if not diag_resp.success or diag_resp.data is None:
        if type(diagnostic_client).__name__ != "ClaudeClient":
            logger.warning(
                "[%s] %s échoué — fallback diagnostic → %s",
                copy_id, type(diagnostic_client).__name__, settings.claude_model_light,
            )
            diag_resp = claude_client.diagnose(result.grade)
    if diag_resp.success and diag_resp.data is not None:
        # ── Orchestrateur ③ : validation diagnostic ───────────────────────────
        vd = validate_diagnostic(diag_resp.data, result.grade)
        result.validation_issues.extend(vd.issues)
        result.diagnostic = vd.data
    else:
        logger.warning("[%s] Diagnostic échoué (non bloquant) : %s", copy_id, diag_resp.error)

    # 7. Sujet de remédiation ─────────────────────────────────────────────────
    if result.diagnostic is not None:
        logger.info("[%s] Génération du sujet de remédiation (%s)…",
                    copy_id, type(remediation_client).__name__)
        rem_resp = remediation_client.generate_remediation_subject(result.diagnostic)
        if not rem_resp.success or rem_resp.data is None:
            if type(remediation_client).__name__ != "ClaudeClient":
                logger.warning(
                    "[%s] %s échoué — fallback remédiation → %s",
                    copy_id, type(remediation_client).__name__, settings.claude_model_heavy,
                )
                rem_resp = claude_client.generate_remediation_subject(result.diagnostic)
        if rem_resp.success and rem_resp.data is not None:
            # ── Orchestrateur ④ : validation remédiation ─────────────────────
            vr = validate_remediation(rem_resp.data, result.diagnostic)
            result.validation_issues.extend(vr.issues)
            result.remediation_subject = vr.data
            logger.info("[%s] %d exercices générés.", copy_id, len(result.remediation_subject.exercises))
        else:
            logger.warning("[%s] Sujet de remédiation non généré (non bloquant) : %s",
                           copy_id, rem_resp.error)

    # 8. Export JSON ────────────────────────────────────────────────────────────
    json_dir = out / copy_id
    json_dir.mkdir(parents=True, exist_ok=True)
    json_path = json_dir / "result.json"
    payload = {
        "copy_id": copy_id,
        "student_name": student_name,
        "quality": result.quality.model_dump(),
        "transcription": result.transcription.model_dump() if result.transcription else None,
        "grade": result.grade.model_dump(),
        "diagnostic": result.diagnostic.model_dump() if result.diagnostic else None,
        "remediation_subject": result.remediation_subject.model_dump() if result.remediation_subject else None,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    result.json_path = json_path

    # 9. Rapport PDF correction ────────────────────────────────────────────────
    logger.info("[%s] Génération PDF rapport correction…", copy_id)
    pdf_path = json_dir / "rapport_correction.pdf"
    generate_copy_report(
        output_path=pdf_path,
        copy_id=copy_id,
        student_name=student_name,
        grade=result.grade,
        diagnostic=result.diagnostic,
        quality=result.quality,
    )
    result.pdf_path = pdf_path

    # 10. PDF sujet de remédiation (document élève) ────────────────────────────
    if result.remediation_subject and result.remediation_subject.exercises:
        logger.info("[%s] Génération PDF sujet de remédiation…", copy_id)
        remediation_pdf_path = json_dir / "sujet_remediation.pdf"
        generate_remediation_pdf(
            output_path=remediation_pdf_path,
            copy_id=copy_id,
            student_name=student_name,
            remediation_subject=result.remediation_subject,
        )
        result.remediation_pdf_path = remediation_pdf_path

    n_exercises = len(result.remediation_subject.exercises) if result.remediation_subject else 0
    logger.warning(
        "[%s] ✓ Pipeline terminé — %d/%d pts | %d exercices remédiation | élève : %s",
        copy_id, result.grade.total_score, result.grade.total_possible,
        n_exercises, result.student_name or "inconnu",
    )
    return result
