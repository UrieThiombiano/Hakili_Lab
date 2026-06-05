"""
Utilitaire de génération d'identifiants sûrs pour le système de fichiers.
L'anonymisation (E-001) a été supprimée — les copies sont identifiées par le nom réel de l'élève.
"""
from __future__ import annotations

import re
import unicodedata


def make_copy_id(name: str, suffix: str = "") -> str:
    """
    Génère un identifiant sûr pour le système de fichiers à partir d'un nom d'élève.
    Ex : "Aminata Sawadogo" → "aminata_sawadogo"
         "Aminata Sawadogo", suffix="2" → "aminata_sawadogo_2"
    """
    normalized = unicodedata.normalize("NFD", name.strip())
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_name.lower()).strip("_")
    base = slug or "copie"
    return f"{base}_{suffix}" if suffix else base
