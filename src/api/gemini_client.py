"""
GeminiTranscriptionClient — transcription via Google Gemini Flash.

Tarifs Gemini 2.0 Flash (2026) :
  - Tier gratuit : 15 RPM, 1 000 000 tokens/jour  → $0 pour une classe entière
  - Tier payant  : $0.10 input / $0.40 output par million de tokens
                   soit ~50× moins cher que Claude Opus 4.7

Ce client remplace ClaudeClient.transcribe() quand VISION_PROVIDER=gemini.
Toutes les autres étapes (correction, diagnostic, remédiation) restent sur Claude.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from PIL import Image

from src.core.config import settings
from src.models.domain import (
    ClaudeResponse,
    PageTranscription,
    TranscriptionResult,
)

logger = logging.getLogger(__name__)

_MAX_PAGES_PER_BATCH = 3   # Gemini gère plusieurs pages par appel → moins d'appels
_MAX_OUTPUT_TOKENS = 4096

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")


# ── Normalisation JSON (identique à ClaudeClient pour cohérence) ──────────────

def _item_to_str(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("expression", "formula", "formule"):
            if key in item:
                val = str(item[key])
                note = item.get("interpretation") or item.get("annotation")
                return f"{val} ({note})" if note else val
        for key in ("zone", "area", "location"):
            if key in item:
                zone = str(item[key])
                note = item.get("note") or item.get("description") or item.get("issue")
                return f"{zone} : {note}" if note else zone
        for key in ("description", "desc", "content"):
            if key in item:
                return str(item[key])
        for v in item.values():
            if v:
                return str(v)
    return str(item)


def _normalize_transcription(data: Any) -> dict:
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return {"copy_id": "unknown", "global_quality": "poor", "pages": []}
    if not isinstance(data, dict):
        return {"copy_id": "unknown", "global_quality": "poor", "pages": []}

    raw_pages = data.get("pages", [])
    if not isinstance(raw_pages, list):
        raw_pages = []

    normalized: list[dict] = []
    for i, page in enumerate(raw_pages):
        if isinstance(page, str):
            normalized.append({
                "page_number": i + 1,
                "content": page,
                "formulas": [],
                "diagrams": [],
                "uncertainties": [],
                "confidence": 0.5,
            })
        elif isinstance(page, dict):
            if not isinstance(page.get("content"), str):
                page["content"] = str(page.get("content") or "")
            for field in ("formulas", "diagrams", "uncertainties"):
                val = page.get(field, [])
                if not isinstance(val, list):
                    val = [val] if val else []
                page[field] = [_item_to_str(x) for x in val if x is not None]
            normalized.append(page)

    data["pages"] = normalized
    return data


def _repair_json(text: str) -> str:
    """Retire les virgules trailing et ferme les accolades/crochets non fermés."""
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


# ── Client principal ──────────────────────────────────────────────────────────

class GeminiTranscriptionClient:
    """Transcription multimodale via Gemini Flash — remplace ClaudeClient.transcribe()."""

    def __init__(self) -> None:
        if not settings.google_api_key:
            raise ValueError(
                "GOOGLE_API_KEY manquante. Ajoutez-la dans .env pour utiliser Gemini."
            )
        self._client = genai.Client(api_key=settings.google_api_key)
        self._transcription_prompt = self._load_prompt("transcription_prompt.md")
        logger.info("GeminiTranscriptionClient initialisé (modèle=%s)", settings.gemini_model)

    def _load_prompt(self, filename: str) -> str:
        prompt_path = Path(__file__).parent.parent.parent / "prompts" / filename
        return prompt_path.read_text(encoding="utf-8")

    # ── API publique (même signature que ClaudeClient.transcribe) ─────────────

    def transcribe(self, copy_id: str, image_paths: list[Path]) -> ClaudeResponse:
        if len(image_paths) <= _MAX_PAGES_PER_BATCH:
            return self._transcribe_batch(copy_id, image_paths, page_offset=0)
        return self._transcribe_batched(copy_id, image_paths)

    # ── Batching ──────────────────────────────────────────────────────────────

    def _transcribe_batched(self, copy_id: str, image_paths: list[Path]) -> ClaudeResponse:
        all_pages: list[PageTranscription] = []
        qualities: list[str] = []

        for start in range(0, len(image_paths), _MAX_PAGES_PER_BATCH):
            batch = image_paths[start : start + _MAX_PAGES_PER_BATCH]
            resp = self._transcribe_batch(copy_id, batch, page_offset=start)
            if not resp.success or resp.data is None:
                return resp
            data: TranscriptionResult = resp.data
            all_pages.extend(data.pages)
            qualities.append(data.global_quality)

        global_quality: str = (
            "poor" if "poor" in qualities
            else "medium" if "medium" in qualities
            else "good"
        )
        merged = TranscriptionResult(
            copy_id=copy_id,
            global_quality=global_quality,  # type: ignore[arg-type]
            pages=all_pages,
        )
        avg_conf = sum(p.confidence for p in all_pages) / len(all_pages) if all_pages else 0.5
        return ClaudeResponse(
            success=True,
            data=merged,
            confidence=avg_conf,
            raw_response=f"[gemini batched {len(all_pages)} pages]",
            error=None,
        )

    def _transcribe_batch(
        self, copy_id: str, image_paths: list[Path], page_offset: int = 0
    ) -> ClaudeResponse:
        page_hint = (
            f"\nCes images sont les pages {page_offset + 1} à {page_offset + len(image_paths)}."
            f" Utilise page_number à partir de {page_offset + 1}."
            if page_offset > 0 else ""
        )

        prompt = (
            f"{self._transcription_prompt}\n\ncopy_id : {copy_id}{page_hint}\n\n"
            "Retourne UNIQUEMENT un objet JSON valide sans aucune balise markdown."
        )

        # Contenu = [texte, image1, image2, ...]
        contents: list[Any] = [prompt]
        for path in image_paths:
            contents.append(Image.open(path))

        try:
            response = self._client.models.generate_content(
                model=settings.gemini_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=_MAX_OUTPUT_TOKENS,
                    temperature=0.1,
                ),
            )

            raw = response.text.strip()

            # Nettoyer les balises markdown si le modèle les ajoute quand même
            m = _JSON_FENCE.search(raw)
            if m:
                raw = m.group(1).strip()

            # Isoler l'objet JSON
            start_idx = raw.find("{")
            end_idx = raw.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                raw = raw[start_idx : end_idx + 1]

            raw = _TRAILING_COMMA.sub(r"\1", raw)

            # Tentative parse → réparation si nécessaire
            data_dict: dict | None = None
            for candidate in (raw, _repair_json(raw)):
                candidate = _TRAILING_COMMA.sub(r"\1", candidate)
                try:
                    data_dict = json.loads(candidate)
                    break
                except json.JSONDecodeError:
                    continue

            if data_dict is None:
                logger.error(
                    "Gemini — JSON irréparable (copy_id=%s, offset=%d). Début : %.300s",
                    copy_id, page_offset, raw,
                )
                return ClaudeResponse(
                    success=False, data=None, confidence=0.0,
                    raw_response=raw[:500],
                    error="JSON invalide retourné par Gemini.",
                )

            data_dict = _normalize_transcription(data_dict)
            validated = TranscriptionResult(**data_dict)

            logger.info(
                "Gemini transcription OK (copy_id=%s, pages=%d-%d, qualité=%s)",
                copy_id, page_offset + 1, page_offset + len(image_paths),
                validated.global_quality,
            )
            return ClaudeResponse(
                success=True,
                data=validated,
                confidence=self._estimate_confidence(validated),
                raw_response=raw[:2000],
                error=None,
            )

        except Exception as e:
            logger.error(
                "Erreur Gemini (copy_id=%s, offset=%d) : %s", copy_id, page_offset, e
            )
            return ClaudeResponse(
                success=False, data=None, confidence=0.0,
                raw_response="",
                error=str(e),
            )

    def _estimate_confidence(self, result: TranscriptionResult) -> float:
        return {"good": 0.9, "medium": 0.7, "poor": 0.5}.get(result.global_quality, 0.5)
