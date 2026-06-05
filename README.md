# Hakili Lab — Correction IA de copies manuscrites

> Outil d'évaluation et de remédiation assistée par IA pour copies manuscrites de **mathématiques**,
> conçu pour le programme du secondaire au **Burkina Faso (6e à Terminale)**.

---

## Vue d'ensemble

Hakili Lab automatise la correction de copies manuscrites numérisées. L'enseignant charge une copie scannée (PDF multi-pages), fournit l'énoncé et le barème, et obtient un **rapport PDF structuré** avec note, commentaires question par question, diagnostic des causes profondes d'erreurs et sujet de remédiation personnalisé.

Le système repose sur une **architecture multi-provider** : chaque tâche est confiée au modèle offrant le meilleur rapport qualité/coût pour cette tâche spécifique. Il applique un **barème binaire strict 0/1** — décision pédagogique volontaire pour des résultats non ambigus et auditables.

**Coût en production : ~$0.02/copie — ~$12/an pour une école standard (540 copies).**

---

## Fonctionnalités

- **Ingestion flexible** — PDF multi-pages, JPG, PNG
- **Contrôle qualité image** — détection du flou (variance du Laplacien), luminosité, résolution minimale
- **Transcription multimodale** — texte, formules mathématiques, schémas ; zones `[ILLISIBLE]` avec score de confiance par page
- **Extraction automatique du barème** — upload d'un PDF barème, extraction structurée sans saisie manuelle
- **Correction selon barème** — évaluation binaire 0/1 par question et sous-question avec commentaire pédagogique
- **Instructions expert optionnelles** — critères d'interprétation injectés dans le prompt pour affiner la correction
- **Diagnostic des causes cachées** — identification des lacunes conceptuelles profondes derrière les erreurs visibles
- **Sujet de remédiation personnalisé** — 5 exercices progressifs par lacune identifiée, en français académique
- **Rapport PDF** — note, détail question par question, confiance IA, diagnostic, sujet de remédiation, logo Hakili Lab
- **Export JSON** — données structurées complètes pour archivage ou traitement ultérieur
- **Validation humaine** — l'enseignant valide sur le rapport PDF exporté, hors plateforme

---

## Architecture et pipeline

```
[Copie PDF multi-pages — scanner 150 DPI]
               │
               ▼
    ┌──────────────────┐
    │    Ingestion     │  PDF → images 150 DPI · nommage page_01, page_02…
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │  Qualité image   │  Flou · luminosité · résolution
    └────────┬─────────┘  ⚠ Avertissement si insuffisant
             │
             ▼
    ┌────────────────────────────────────────────────┐
    │  Transcription  (Gemini 2.0 Flash)             │
    │  texte + formules + schémas + [ILLISIBLE]      │
    │  3 pages/appel · tier gratuit 1M tokens/jour   │
    └────────┬───────────────────────────────────────┘
             │
             ▼
    ┌────────────────────────────────────────────────┐
    │  Correction  (DeepSeek V3)                     │
    │  score 0/1 · commentaire · requires_review     │
    │  MATH-500 ~90% · meilleur raisonnement math    │
    └────────┬───────────────────────────────────────┘
             │
             ▼
    ┌────────────────────────────────────────────────┐
    │  Diagnostic  (DeepSeek R1)                     │
    │  causes cachées · compétences · remédiation    │
    │  modèle de raisonnement chain-of-thought       │
    └────────┬───────────────────────────────────────┘
             │
             ▼
    ┌────────────────────────────────────────────────┐
    │  Remédiation  (Mistral Small 3.1)              │
    │  5 exercices/lacune · français académique      │
    └────────┬───────────────────────────────────────┘
             │
             ▼
    ┌─────────────────────┐
    │   PDF + JSON + UI   │  Rapport · Export · Téléchargement
    └─────────────────────┘
```

**Routing automatique :** si une clé API est absente ou si le provider échoue (quota épuisé, solde insuffisant, erreur réseau), le pipeline bascule sur Claude — aucune interruption.

| Tâche | Fallback | Modèle Claude |
|---|---|---|
| Transcription | Claude | Sonnet 4.6 |
| Correction | Claude | Sonnet 4.6 |
| Diagnostic | Claude | Haiku 4.5 |
| Remédiation | Claude | Sonnet 4.6 |

---

## Providers IA par tâche

| Tâche | Provider | Modèle | Justification | Coût/copie |
|---|---|---|---|---|
| Transcription | **Google Gemini** | gemini-2.0-flash | Vision native, tier gratuit 1M tok/j | $0.00 |
| Correction | **DeepSeek** | deepseek-chat (V3) | MATH-500 ~90%, meilleur score math | $0.005 |
| Diagnostic | **DeepSeek** | deepseek-reasoner (R1) | Chain-of-thought, causes profondes | $0.008 |
| Remédiation | **Mistral** | mistral-small-latest | Français académique natif | $0.003 |
| Barème/Énoncé | **Claude** | claude-sonnet-4-6 | tool_use forcé, extraction fiable | $0.010 |
| **Total** | | | | **~$0.02** |

> Analyse complète : [docs/ai_providers_analysis.md](docs/ai_providers_analysis.md)

---

## Stack technique

| Couche | Technologie |
|---|---|
| Interface | Streamlit |
| IA — Vision | Google Gemini 2.0 Flash |
| IA — Raisonnement math | DeepSeek V3 + R1 (API compatible OpenAI) |
| IA — Génération French | Mistral Small 3.1 |
| IA — Extraction structurée | Anthropic Claude Sonnet 4.6 |
| Modèles de données | Pydantic v2 + pydantic-settings |
| PDF → images | PyMuPDF (fitz) · 150 DPI |
| Qualité image | OpenCV + Pillow |
| Génération PDF | ReportLab |
| Retry API | Tenacity |
| Tests | Pytest |
| Linting / typage | Ruff + MyPy |

---

## Prérequis

- **Python 3.11 ou supérieur**
- **Clé API Anthropic** (obligatoire — fallback) — [console.anthropic.com](https://console.anthropic.com)
- **Clé API Google AI Studio** (recommandé — tier gratuit) — [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
- **Clé API DeepSeek** (recommandé) — [platform.deepseek.com](https://platform.deepseek.com/api_keys)
- **Clé API Mistral** (recommandé) — [console.mistral.ai](https://console.mistral.ai/api-keys)

---

## Démarrage rapide

### Windows (PowerShell)

```powershell
# 1. Activer l'environnement virtuel
.\.venv\Scripts\Activate.ps1

# 2. Lancer l'interface
streamlit run src\ui\app.py
```

> Si PowerShell bloque : `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### Linux / Mac

```bash
source .venv/bin/activate
streamlit run src/ui/app.py
# ou
make run
```

L'interface s'ouvre sur `http://localhost:8501`.

---

## Installation

### Windows (PowerShell)

```powershell
git clone <url-du-repo>
cd hakili_ai_correction

python -m venv .venv
.\.venv\Scripts\pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt

Copy-Item .env.example .env
# Ouvrir .env et renseigner les clés API
.\.venv\Scripts\streamlit.exe run src\ui\app.py
```

### Linux / Mac

```bash
git clone <url-du-repo>
cd hakili_ai_correction
make setup
cp .env.example .env
# Éditer .env avec les clés API
make run
```

---

## Configuration (`.env`)

```env
# ── Anthropic Claude (obligatoire — fallback + extraction) ───────────────────
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL_HEAVY=claude-sonnet-4-6

# ── Google Gemini — transcription vision (GRATUIT jusqu'à 1M tokens/jour) ────
# Clé gratuite : https://aistudio.google.com/apikey
GOOGLE_API_KEY=AIza...
VISION_PROVIDER=gemini          # "gemini" | "claude"

# ── DeepSeek — correction (V3) + diagnostic (R1) ─────────────────────────────
# Clé : https://platform.deepseek.com/api_keys
DEEPSEEK_API_KEY=sk-...

# ── Mistral — remédiation français académique ─────────────────────────────────
# Clé : https://console.mistral.ai/api-keys
MISTRAL_API_KEY=...

# ── Seuils qualité image ──────────────────────────────────────────────────────
CONFIDENCE_REVIEW_THRESHOLD=0.75
IMAGE_MIN_RESOLUTION=1000
IMAGE_BLUR_THRESHOLD=100.0

# ── Stockage local ────────────────────────────────────────────────────────────
RUNS_DIR=./runs
```

---

## Utilisation

### Mode Copie unique

1. Aller sur l'onglet **Traitement unique**
2. Charger la copie (PDF scanner recommandé, 150 DPI, niveaux de gris)
3. Charger l'énoncé (optionnel — PDF ou image)
4. Charger le barème (PDF) ou saisir ligne par ligne (`Q1 : libellé`)
5. Renseigner le nom de l'élève et la classe
6. Ajouter des instructions expert si nécessaire
7. Cliquer **Lancer l'analyse**
8. Télécharger le rapport PDF

### Format du barème (saisie textuelle)

```
Q1 : Résoudre le système d'équations
Q2a : Calculer la limite de f en +∞
Q2b : Étudier la dérivabilité de f en 0
Q3 : Tracer la courbe représentative
```

Si le champ barème est laissé vide, le système détecte automatiquement les questions.

### Recommandation matériel de scan

| Contexte | Recommandation | Réglages |
|---|---|---|
| Usage régulier | Scanner ADF (ex. Epson ES-65W ~$130) | 150 DPI · niveaux de gris · PDF |
| Usage occasionnel | Multifonction école | 150 DPI · niveaux de gris · PDF |
| Terrain / urgence | Smartphone + Microsoft Lens | Mode Document → PDF |

> Analyse détaillée : [docs/input_pipeline_analysis.md](docs/input_pipeline_analysis.md)

---

## Structure du projet

```
hakili_ai_correction/
│
├── src/
│   ├── api/
│   │   ├── claude_client.py      # Claude : extraction barème/énoncé · fallback
│   │   ├── gemini_client.py      # Gemini 2.0 Flash : transcription vision
│   │   ├── deepseek_client.py    # DeepSeek V3 : correction · R1 : diagnostic
│   │   └── mistral_client.py     # Mistral Small : remédiation français
│   ├── core/
│   │   ├── config.py             # Pydantic Settings (.env) — tous providers
│   │   └── anonymizer.py         # Génération slug copy_id
│   ├── models/
│   │   └── domain.py             # Modèles Pydantic : Rubric, CopyGrade, DiagnosticResult…
│   ├── pipeline/
│   │   ├── ingestion.py          # PDF → images 150 DPI · multi-images
│   │   ├── image_quality.py      # Contrôle qualité (OpenCV + PIL)
│   │   ├── pipeline.py           # Orchestrateur multi-provider avec routing automatique
│   │   └── pdf_report.py         # Génération rapport PDF (ReportLab)
│   └── ui/
│       └── app.py                # Interface Streamlit
│
├── prompts/
│   ├── transcription_prompt.md   # Instructions transcription multimodale
│   ├── grading_prompt.md         # Instructions correction selon barème
│   ├── diagnostic_prompt.md      # Instructions diagnostic causes cachées
│   └── remediation_subject_prompt.md  # Instructions génération exercices
│
├── docs/
│   ├── decision_register.md      # Registre des décisions structurantes
│   ├── ai_providers_analysis.md  # Analyse comparative LLM par tâche
│   └── input_pipeline_analysis.md # Analyse OCR vs LLM + format d'entrée optimal
│
├── tests/
│   └── test_models.py
│
├── runs/                         # Sorties pipeline (local · non versionné)
│
├── .env.example
├── .env
├── requirements.txt
├── Makefile
└── CLAUDE.md
```

---

## Commandes développement

| Commande | Description |
|---|---|
| `make setup` | Créer le venv et installer les dépendances |
| `make run` | Lancer l'interface Streamlit |
| `make test` | Lancer les tests unitaires |
| `make lint` | Vérifier qualité du code (ruff + mypy) |

**Sans make (Windows) :**

```powershell
.\.venv\Scripts\pytest tests/ -v
.\.venv\Scripts\ruff check src/
.\.venv\Scripts\streamlit.exe run src\ui\app.py
```

---

## Décisions structurantes

| ID | Sujet | Décision |
|---|---|---|
| D-CEO-01 | Matières et niveaux | Mathématiques, **6e à la Terminale** |
| D-CEO-02 | Format barème | Binaire 0/1 par question et sous-question |
| D-CEO-03 | Stratégie IA | **Multi-provider** avec routing automatique |
| D-CEO-04 | Instructions expert | Couche optionnelle d'instructions contextuelles |
| D-CEO-05 | Validation humaine | Hors plateforme (enseignant sur PDF exporté) |
| D-CEO-07 | Identification | Nom réel de l'élève (slug technique pour fichiers) |
| D-CEO-10 | Format entrée optimal | **PDF scanner 150 DPI** niveaux de gris |
| D-CEO-11 | Coût cible | ~$0.02/copie · ~$12/an pour 540 copies |

Registre complet : [docs/decision_register.md](docs/decision_register.md)

---

## Limitations connues (prototype)

- Copie très dégradée (photo floue, faible éclairage) → confiance IA réduite
- Formules très complexes (intégrales multiples, matrices) → transcription approximative possible
- Écriture cursive très dense → zones `[ILLISIBLE]` possibles
- Français uniquement
- Stockage local uniquement (pas de déploiement cloud dans l'état)

---

## Objectifs de validation

| Objectif | Cible |
|---|---|
| Précision correction (IA vs enseignant) | ≤ 1 point d'écart sur barème 10 pts |
| Taux de révision humaine requise | < 15% des questions |
| Temps de traitement par copie | < 120 secondes |
| Volume cible de validation | 100 copies réelles avec enseignant référent |

---

*Prototype confidentiel — Hakili Lab · Usage pédagogique exclusif · Burkina Faso*
