import json
import re
from pathlib import Path
from typing import Any

import anthropic
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from src.core.config import settings
from src.models.domain import (
    ClaudeResponse,
    CopyGrade,
    DiagnosticResult,
    Rubric,
    TranscriptionResult,
)

_MEDIA_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _is_retryable(exc: BaseException) -> bool:
    """Retente sur surcharge (529) et erreurs réseau transitoires."""
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code in (429, 529)
    return isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError))


_retry = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(6),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    reraise=True,
)


class ClaudeClient:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._transcription_prompt = self._load_prompt("transcription_prompt.md")
        self._grading_prompt = self._load_prompt("grading_prompt.md")
        self._diagnostic_prompt = self._load_prompt("diagnostic_prompt.md")

    def _load_prompt(self, filename: str) -> str:
        prompt_path = Path(__file__).parent.parent.parent / "prompts" / filename
        return prompt_path.read_text(encoding="utf-8")

    @_retry
    def transcribe(self, copy_id: str, image_paths: list[Path]) -> ClaudeResponse:
        """Transcrit les images en utilisant Claude Vision avec prompt caching."""
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": self._transcription_prompt,
                "cache_control": {"type": "ephemeral"},  # prompt statique → cache
            },
            {
                "type": "text",
                "text": f"copy_id à utiliser dans ta réponse JSON : {copy_id}",
            },
            *[
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": self._media_type(path),
                        "data": self._encode_image(path),
                    },
                }
                for path in image_paths
            ],
        ]

        response = self.client.messages.create(
            model=settings.claude_model_heavy,
            max_tokens=4096,
            messages=[{"role": "user", "content": content}],
        )

        return self._parse_response(response.content[0].text, TranscriptionResult)

    @_retry
    def grade(
        self,
        transcription: TranscriptionResult,
        rubric: Rubric,
        subject_text: str,
        expert_instructions: str = "",
    ) -> ClaudeResponse:
        """Corrige la copie selon le barème. Injecte l'énoncé et les instructions expert."""
        expert_block = f"\n\nINSTRUCTIONS EXPERT:\n{expert_instructions}" if expert_instructions.strip() else ""

        auto_block = ""
        if not rubric.items:
            auto_block = (
                "\n\nINSTRUCTION SPÉCIALE : Aucun barème n'a été fourni. "
                "Identifie automatiquement toutes les questions présentes dans la copie "
                "et évalue chacune sur 0 ou 1 (barème binaire strict). "
                "Génère les identifiants au format Q1, Q2a, Q2b, etc."
            )

        prompt = (
            f"{self._grading_prompt}{auto_block}{expert_block}"
            f"\n\nÉNONCÉ:\n{subject_text}"
            f"\n\nBARÈME:\n{rubric.model_dump_json(indent=2)}"
            f"\n\nTRANSCRIPTION:\n{transcription.model_dump_json(indent=2)}"
        )

        response = self.client.messages.create(
            model=settings.claude_model_heavy,
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                }
            ],
        )

        result = self._parse_response(response.content[0].text, CopyGrade)
        if result.success and result.data is not None and expert_instructions.strip():
            result.data.expert_instructions_used = True
        return result

    @_retry
    def diagnose(self, grades: CopyGrade) -> ClaudeResponse:
        """Produit le diagnostic pédagogique."""
        prompt = (
            f"{self._diagnostic_prompt}"
            f"\n\nRÉSULTATS DE CORRECTION:\n{grades.model_dump_json(indent=2)}"
        )

        response = self.client.messages.create(
            model=settings.claude_model_light,
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                }
            ],
        )

        return self._parse_response(response.content[0].text, DiagnosticResult)

    def extract_subject(self, file_path: Path) -> str:
        """Extrait le texte d'un énoncé depuis une image ou un PDF."""
        images = self._pdf_to_images(file_path) if file_path.suffix.lower() == ".pdf" else [file_path]
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "Transcris intégralement le texte de cet énoncé. "
                    "Retourne uniquement le texte brut, sans JSON, sans commentaire."
                ),
            },
            *[
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": self._media_type(img),
                        "data": self._encode_image(img),
                    },
                }
                for img in images
            ],
        ]
        response = self.client.messages.create(
            model=settings.claude_model_light,
            max_tokens=2048,
            messages=[{"role": "user", "content": content}],
        )
        return response.content[0].text.strip()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _media_type(self, path: Path) -> str:
        return _MEDIA_TYPES.get(path.suffix.lower(), "image/jpeg")

    def _encode_image(self, path: Path) -> str:
        import base64
        return base64.b64encode(path.read_bytes()).decode("utf-8")

    def _pdf_to_images(self, pdf_path: Path) -> list[Path]:
        import fitz
        import tempfile
        tmp_dir = Path(tempfile.mkdtemp())
        doc = fitz.open(pdf_path)
        images: list[Path] = []
        for i in range(len(doc)):
            pix = doc.load_page(i).get_pixmap(dpi=150)
            img_path = tmp_dir / f"subject_page_{i+1}.jpg"
            pix.save(str(img_path))
            images.append(img_path)
        doc.close()
        return images

    def _parse_response(self, raw_text: str, model_cls: type) -> ClaudeResponse:
        """Parse la réponse JSON — gère les blocs markdown ```json ... ```."""
        text = raw_text.strip()
        match = _JSON_FENCE.search(text)
        if match:
            text = match.group(1).strip()

        try:
            data = json.loads(text)
            validated = model_cls(**data)
            return ClaudeResponse(
                success=True,
                data=validated,
                confidence=self._estimate_confidence(validated),
                raw_response=raw_text,
                error=None,
            )
        except Exception as e:
            return ClaudeResponse(
                success=False,
                data=None,
                confidence=0.0,
                raw_response=raw_text,
                error=str(e),
            )

    def _estimate_confidence(self, result: Any) -> float:
        if hasattr(result, "global_quality"):
            return {"good": 0.9, "medium": 0.7, "poor": 0.5}.get(result.global_quality, 0.5)
        if hasattr(result, "questions"):
            confidences = [q.confidence for q in result.questions if hasattr(q, "confidence")]
            return sum(confidences) / len(confidences) if confidences else 0.5
        return 0.8
