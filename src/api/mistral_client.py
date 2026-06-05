"""
MistralRemediationClient — génération du sujet de remédiation via Mistral Small 3.1.

Avantage clé : Mistral est une société française dont les modèles sont entraînés
sur des corpus pédagogiques francophones natifs (manuels, annales, exercices scolaires).
La qualité du français académique et de la terminologie mathématique francophone
est supérieure à Gemini ou DeepSeek pour cette tâche de génération.

Coût : $0.10/$0.30 par million de tokens.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from mistralai.client import Mistral
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from src.core.config import settings
from src.models.domain import ClaudeResponse, DiagnosticResult, RemediationSubject

logger = logging.getLogger(__name__)

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")


# ── Utilitaires JSON ──────────────────────────────────────────────────────────

def _repair_json(text: str) -> str:
    stack: list[str] = []
    in_string = False
    i = 0
    while i < len(text):
        c = text[i]
        if c == "\\" and in_string:
            i += 2
            continue
        if c == '"':
            in_string = not in_string
        elif not in_string:
            if c in ("{", "["):
                stack.append(c)
            elif c in ("}", "]") and stack:
                stack.pop()
        i += 1
    close_map = {"[": "]", "{": "}"}
    return text + "".join(close_map[c] for c in reversed(stack))


def _parse_json_response(raw: str, model_cls: type) -> ClaudeResponse:
    text = raw.strip()
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    text = _TRAILING_COMMA.sub(r"\1", text)

    for candidate in (text, _repair_json(text)):
        candidate = _TRAILING_COMMA.sub(r"\1", candidate)
        try:
            data = json.loads(candidate)
            validated = model_cls(**data)
            return ClaudeResponse(
                success=True, data=validated, confidence=0.88,
                raw_response=raw[:2000], error=None,
            )
        except (json.JSONDecodeError, Exception):
            continue

    logger.error("Mistral — JSON irréparable (%s). Début : %.300s", model_cls.__name__, raw)
    return ClaudeResponse(
        success=False, data=None, confidence=0.0,
        raw_response=raw[:500],
        error=f"JSON invalide retourné par Mistral. Début : {raw[:200]}",
    )


def _load_prompt(filename: str) -> str:
    prompt_path = Path(__file__).parent.parent.parent / "prompts" / filename
    return prompt_path.read_text(encoding="utf-8")


# ── Retry ─────────────────────────────────────────────────────────────────────

def _is_retryable_mistral(exc: BaseException) -> bool:
    # Mistral SDK lève des HTTPStatusError (httpx) pour 429/500
    name = type(exc).__name__
    return "RateLimit" in name or "Timeout" in name or "Connection" in name


_retry = retry(
    retry=retry_if_exception(_is_retryable_mistral),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    reraise=True,
)


# ── Client principal ──────────────────────────────────────────────────────────

class MistralRemediationClient:
    """Génération d'exercices de remédiation en français académique via Mistral Small."""

    def __init__(self) -> None:
        if not settings.mistral_api_key:
            raise ValueError(
                "MISTRAL_API_KEY manquante. Ajoutez-la dans .env pour utiliser Mistral."
            )
        self._client = Mistral(api_key=settings.mistral_api_key)
        self._remediation_prompt = _load_prompt("remediation_subject_prompt.md")
        logger.info("MistralRemediationClient initialisé (modèle=%s)", settings.mistral_model)

    @_retry
    def generate_remediation_subject(self, diagnostic: DiagnosticResult) -> ClaudeResponse:
        """
        Génère 5 exercices progressifs par difficulté identifiée.

        Mistral Small 3.1 — français académique natif, terminologie CEDEAO/UEMOA.
        """
        logger.info("[%s] Mistral remédiation — modèle : %s | difficultés : %d",
                    diagnostic.copy_id, settings.mistral_model,
                    len(diagnostic.weaknesses) or len(diagnostic.root_causes))
        if not diagnostic.weaknesses and not diagnostic.root_causes:
            return ClaudeResponse(
                success=False, data=None, confidence=0.0,
                raw_response="",
                error="Aucune difficulté identifiée — pas de sujet de remédiation à générer.",
            )

        n_series = len(diagnostic.weaknesses) or len(diagnostic.root_causes)
        user_content = (
            f"{self._remediation_prompt}"
            f"\n\n---\n\nDIAGNOSTIC ({n_series} difficulté(s) à couvrir):\n"
            f"{diagnostic.model_dump_json(indent=2)}"
        )

        try:
            response = self._client.chat.complete(
                model=settings.mistral_model,
                messages=[{"role": "user", "content": user_content}],
                response_format={"type": "json_object"},
                max_tokens=8192,
                temperature=0.4,   # Légère créativité pour varier les exercices
            )
            raw = response.choices[0].message.content or ""
            logger.info(
                "Mistral remédiation OK — tokens: %d in / %d out",
                response.usage.prompt_tokens, response.usage.completion_tokens,
            )
            return _parse_json_response(raw, RemediationSubject)
        except Exception as e:
            logger.error("Mistral generate_remediation_subject erreur : %s", e)
            return ClaudeResponse(success=False, data=None, confidence=0.0,
                                  raw_response="", error=str(e))
