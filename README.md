# Hakili Lab — Correction IA de copies manuscrites

> Outil d'évaluation et de remédiation assistée par IA pour copies manuscrites de **mathématiques**,
> conçu pour le programme du secondaire au **Burkina Faso (3e et Terminale)**.

---

## Vue d'ensemble

Hakili Lab automatise la correction de copies manuscrites numérisées. L'enseignant charge une copie (scan ou photo), fournit l'énoncé et le barème, et obtient en retour un **rapport PDF structuré** avec note, commentaires question par question, diagnostic pédagogique et plan de remédiation personnalisé.

Le système repose sur **Claude d'Anthropic** (vision multimodale) et applique un **barème binaire strict 0/1** — décision pédagogique volontaire pour garantir des résultats non ambigus et auditables.

### Cas d'usage principaux

| Mode | Description |
|---|---|
| **Copie unique** | Correction immédiate d'une seule copie, résultat affiché et téléchargeable |
| **Batch** | Session multi-élèves : toutes les copies d'une classe traitées en séquence, avec synthèse globale |

---

## Fonctionnalités

- **Ingestion flexible** — PDF multi-pages, JPG, PNG ; conversion automatique en images haute résolution (300 dpi)
- **Contrôle qualité image** — détection du flou (variance du Laplacien), luminosité insuffisante, résolution minimale
- **Transcription multimodale** — texte, formules mathématiques, schémas ; signalement des zones `[ILLISIBLE]` avec score de confiance par page
- **Correction selon barème** — évaluation binaire 0/1 par question et sous-question avec commentaire pédagogique
- **Instructions expert** — critères d'interprétation optionnels injectés dans le prompt pour affiner la précision sur un devoir spécifique
- **Diagnostic pédagogique** — forces, lacunes par compétence, plan de remédiation priorisé sur 1 à 2 semaines
- **Rapport PDF** — note, détail question par question, confiance IA, diagnostic, logo Hakili Lab
- **Export JSON** — données structurées pour archivage ou traitement ultérieur
- **Anonymisation automatique** — les copies sont traitées sous `E-001`, `E-002`… ; la fiche de correspondance `nom ↔ identifiant` est séparée et ne figure jamais dans les rapports
- **Validation humaine** — l'enseignant valide sur le rapport PDF exporté, hors plateforme

---

## Architecture et pipeline

```
Copie PDF / Image(s)
        │
        ▼
┌───────────────┐
│   Ingestion   │  PDF → images JPG (300 dpi) · nommage page_01, page_02…
└───────┬───────┘
        │
        ▼
┌───────────────────┐
│  Qualité image    │  Flou · luminosité · résolution
└───────┬───────────┘  ⚠ Avertissement si insuffisant (traitement poursuivi)
        │
        ▼
┌─────────────────────────────────────────────────┐
│  Transcription  (claude-opus-4-7)               │
│  texte + formules + schémas + [ILLISIBLE]       │
│  confiance par page · prompt caching activé     │
└───────┬─────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│  Correction  (claude-opus-4-7)                           │
│  score 0/1 par question · commentaire · requires_review  │
│  + instructions expert optionnelles                      │
└───────┬──────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────┐
│  Diagnostic  (claude-haiku-4-5)                 │
│  forces · lacunes · compétences · remédiation   │
└───────┬─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────┐
│  PDF + JSON + UI    │  Rapport · Export · Téléchargement
└─────────────────────┘
```

**Deux modèles sont utilisés :**
- `claude-opus-4-7` — tâches de raisonnement complexe (transcription, correction)
- `claude-haiku-4-5` — tâches légères (diagnostic pédagogique) pour réduire la latence et le coût

---

## Stack technique

| Couche | Technologie |
|---|---|
| Interface | Streamlit 1.36 |
| IA | Anthropic Claude (API officielle + SDK Python) |
| Modèles de données | Pydantic v2 + pydantic-settings |
| PDF → images | PyMuPDF (fitz) |
| Qualité image | OpenCV + Pillow |
| Génération PDF | ReportLab |
| Retry API | Tenacity |
| Tests | Pytest |
| Linting / typage | Ruff + MyPy |

---

## Prérequis

- **Python 3.11 ou supérieur**
- **Clé API Anthropic** — [console.anthropic.com](https://console.anthropic.com)
- `make` optionnel — Linux/Mac natif · Windows : `winget install GnuWin32.Make`

---

## Démarrage rapide (après installation)

Une fois le projet installé et `.env` configuré, voici les commandes à lancer à chaque session :

### Windows (PowerShell)

```powershell
# 1. Activer l'environnement virtuel
.\.venv\Scripts\Activate.ps1

# 2. Lancer l'interface
streamlit run src\ui\app.py
```

> Si PowerShell bloque l'exécution des scripts, lancer une fois :
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### Linux / Mac

```bash
# 1. Activer l'environnement virtuel
source .venv/bin/activate

# 2. Lancer l'interface
streamlit run src/ui/app.py
# ou
make run
```

L'interface s'ouvre automatiquement sur `http://localhost:8501`.

---

## Installation

### Windows (PowerShell)

```powershell
git clone <url-du-repo>
cd hakili_ai_correction

# Créer l'environnement virtuel et installer les dépendances
python -m venv .venv
.\.venv\Scripts\pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt

# Configurer la clé API
Copy-Item .env.example .env
# Ouvrir .env et renseigner ANTHROPIC_API_KEY

# Lancer l'interface
.\.venv\Scripts\streamlit.exe run src\ui\app.py
```

### Linux / Mac

```bash
git clone <url-du-repo>
cd hakili_ai_correction
make setup          # crée .venv + installe les dépendances
cp .env.example .env
# Éditer .env avec ANTHROPIC_API_KEY
make run
```

---

## Configuration (`.env`)

```env
# Obligatoire
ANTHROPIC_API_KEY=sk-ant-...

# Modèles Claude (ne pas modifier sans raison valable)
CLAUDE_MODEL_HEAVY=claude-opus-4-7            # transcription + correction
CLAUDE_MODEL_LIGHT=claude-haiku-4-5-20251001  # diagnostic pédagogique

# Seuils de qualité image
CONFIDENCE_REVIEW_THRESHOLD=0.75   # en dessous : révision humaine requise
IMAGE_MIN_RESOLUTION=1000          # pixels (largeur ou hauteur)
IMAGE_BLUR_THRESHOLD=100.0         # variance Laplacien min

# Stockage local des sorties
RUNS_DIR=./runs
```

---

## Utilisation

### Mode Copie unique

1. Aller sur l'onglet **Traitement unique**
2. Charger la copie (PDF ou image)
3. Charger l'énoncé (optionnel — PDF ou image)
4. Saisir le barème ligne par ligne (`Q1 : libellé`) ou laisser vide pour détection automatique
5. Renseigner le nom de l'élève et la classe
6. Ajouter des instructions expert si nécessaire (ex : *"Accepter x = 0 même sans justification pour Q2b"*)
7. Cliquer **Lancer l'analyse**
8. Télécharger le rapport PDF, le JSON ou la fiche de correspondance

### Mode Batch

1. Aller sur l'onglet **Traitement batch**
2. Renseigner le nom du devoir (ex : `DS1 — Fonctions numériques`), la classe, la date
3. Charger l'énoncé commun et le barème
4. Charger toutes les copies (nommer les fichiers avec le nom de l'élève : `sawadogo_aminata.pdf`)
5. Cliquer **Lancer le traitement batch**
6. Consulter la synthèse de classe (moyenne, tableau de notes)
7. Télécharger les rapports individuels et la fiche de correspondance

### Format du barème (saisie textuelle)

```
Q1 : Résoudre le système d'équations
Q2a : Calculer la limite de f en +∞
Q2b : Étudier la dérivabilité de f en 0
Q3 : Tracer la courbe représentative
```

Si le champ barème est laissé **vide**, Claude détecte automatiquement toutes les questions et attribue un score 0/1 à chacune.

---

## Structure du projet

```
hakili_ai_correction/
│
├── src/
│   ├── api/
│   │   └── claude_client.py      # Client Anthropic : transcription, correction, diagnostic
│   │                              # retry intelligent (529/429/timeout) · prompt caching
│   ├── core/
│   │   ├── config.py             # Pydantic Settings (.env)
│   │   └── anonymizer.py         # Numérotation E-001… + CSV de correspondance persistant
│   ├── models/
│   │   └── domain.py             # Modèles Pydantic : Rubric, CopyGrade, TranscriptionResult…
│   ├── pipeline/
│   │   ├── ingestion.py          # PDF → images haute résolution · multi-images
│   │   ├── image_quality.py      # Contrôle qualité (OpenCV + PIL)
│   │   ├── pipeline.py           # Orchestrateur : ingestion → PDF export
│   │   └── pdf_report.py         # Génération rapport PDF (ReportLab)
│   └── ui/
│       ├── app.py                # Interface Streamlit (Unique · Batch · À propos)
│       └── hakili_logo.png       # Logo (en-tête PDF + sidebar)
│
├── prompts/
│   ├── transcription_prompt.md   # Instructions transcription multimodale
│   ├── grading_prompt.md         # Instructions correction selon barème
│   └── diagnostic_prompt.md      # Instructions diagnostic + remédiation
│
├── data/
│   └── schemas/                  # Schémas JSON de validation (Pydantic ↔ Claude)
│       ├── transcription.schema.json
│       ├── grading.schema.json
│       ├── diagnostic.schema.json
│       ├── rubric.schema.json
│       ├── ingestion.schema.json
│       └── claude_response.schema.json
│
├── tests/
│   └── test_models.py            # Tests unitaires modèles Pydantic
│
├── docs/
│   └── decision_register.md      # Registre des décisions structurantes (D-CEO-01…)
│
├── runs/                         # Sorties pipeline (local · non versionné)
│   └── <copy_id>/
│       ├── pages/                # Images extraites
│       ├── result.json           # Données structurées complètes
│       └── rapport.pdf           # Rapport enseignant
│
├── .env.example                  # Template de configuration
├── .env                          # Variables d'environnement (non versionné)
├── requirements.txt              # Dépendances Python épinglées
├── Makefile                      # Automatisation (setup · run · test · lint)
├── setup.ps1                     # Script setup Windows alternatif
└── CLAUDE.md                     # Instructions pour Claude Code (développement)
```

---

## Commandes développement

| Commande | Description |
|---|---|
| `make setup` | Créer le venv et installer les dépendances |
| `make run` | Lancer l'interface Streamlit |
| `make test` | Lancer les tests unitaires (pytest) |
| `make lint` | Vérifier qualité du code (ruff + mypy) |
| `make clean` | Nettoyer les caches Python |

**Sans make (Windows) :**

```powershell
# Tests
.\.venv\Scripts\pytest tests/ -v

# Linter
.\.venv\Scripts\ruff check src/
.\.venv\Scripts\mypy src/

# Interface
.\.venv\Scripts\streamlit.exe run src\ui\app.py
```

---

## Décisions structurantes

Registre complet : [docs/decision_register.md](docs/decision_register.md)

| ID | Décision | Justification |
|---|---|---|
| D-CEO-01 | Mathématiques uniquement pour le MVP | Réduire la complexité initiale ; extension possible |
| D-CEO-02 | Barème binaire 0/1 strict | Résultats non ambigus, auditables, cohérents avec la pratique enseignante |
| D-CEO-03 | Claude exclusivement (Anthropic) | Meilleure capacité de vision multimodale sur écriture manuscrite |
| D-CEO-04 | Instructions expert optionnelles | Personnalisation sans modifier les prompts de base |
| D-CEO-05 | Validation humaine hors plateforme | L'IA assiste, l'enseignant décide |
| D-CEO-06 | Rapport PDF 7 éléments | Note · commentaires · révisions · diagnostic · remédiation · confiance · logo |
| D-CEO-07 | Anonymisation automatique | Protection des données élèves dès le prototype |
| D-CEO-09 | Deux modes d'interface | Copie unique (test rapide) + Batch (usage classe réel) |

---

## Confidentialité et données

- Toutes les données sont stockées **localement** dans `runs/` — aucun envoi cloud hors appels API Anthropic
- Les noms d'élèves sont remplacés par `E-001`, `E-002`… **avant** tout envoi à l'API
- La fiche de correspondance `nom ↔ identifiant` est un fichier CSV séparé, téléchargeable à part, jamais incluse dans les rapports PDF
- Les logs ne contiennent aucune donnée personnelle identifiable

---

## Limitations connues (prototype)

- Copie très dégradée (photo floue, faible éclairage) → confiance IA réduite, révision humaine recommandée
- Formules complexes (intégrales multiples, matrices) → transcription approximative possible
- Écriture cursive dense → zones `[ILLISIBLE]` possibles
- Pas de support multilingue (français uniquement)
- Pas de déploiement cloud dans l'état actuel (stockage local uniquement)

---

## Objectifs de validation

| Objectif | Cible |
|---|---|
| Précision correction (IA vs enseignant) | ≤ 1 point d'écart sur barème 10 pts, avec instructions expert |
| Taux de révision humaine requise | < 15 % des questions |
| Temps de traitement par copie | < 90 secondes |
| Volume cible de validation | 100 copies réelles avec enseignant référent |

---

*Prototype confidentiel — Hakili Lab · Usage pédagogique exclusif · Burkina Faso*
