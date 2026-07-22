# Registre des Décisions — Hakili Lab AI Correction
**Mis à jour le : 2026-06-11 (réorientation vers correction assistée)**

---

## Décisions initiales d'architecture (fondations techniques)

| ID | Décision | Statut | Justification |
|---|---|---|---|
| D001 | Ingestion par copie complète PDF/images, pas question par question | **Validée** | Plus rapide, moins fastidieux, meilleur flux terrain |
| D002 | JSON structuré comme source de vérité, PDF comme rendu | **Validée** | Facilite évaluation, audit et réutilisation |
| D003 | Streamlit pour l'interface MVP | **Validée** | Plus rapide à implémenter en Python |
| D004 | Stockage local anonymisé pour prototype | **Validée** | Simplicité + confidentialité |
| D005 | Évaluation sur 100 copies avec enseignant référent | **Validée** | Exigence du cahier de charges |

---

## Décisions CEO — 2026-05-08

### D-CEO-01 — Périmètre matières et niveaux du MVP
**Décision :** Mathématiques uniquement, tous niveaux du secondaire : **6e à la Terminale**.

---

### D-CEO-02 — Format du barème
**Décision :** Notation binaire — **1 ou 0** par question (ou sous-question).

**Règle métier clé :** Une question comportant N sous-questions est décomposée en N questions indépendantes, chacune valant 1 point. Il n'y a pas de notation partielle : une réponse est correcte (1) ou incorrecte (0).

*Exemple : Question 3 avec 3 sous-questions → Q3a (1 pt), Q3b (1 pt), Q3c (1 pt). La note de Q3 = somme des sous-questions.*

**Impact :** Le module de parsing du barème et le schéma `grading.json` sont simplifiés : `max_score` est toujours un entier, `score` est toujours 0 ou 1 par item.

---

### D-CEO-03 — Stratégie fournisseurs IA *(révisée 2026-06-05)*
**Décision initiale (2026-05-08) :** Anthropic Claude exclusivement.
**Décision révisée (2026-06-05) :** **Architecture multi-provider avec routing automatique par tâche.**

**Contexte de révision :** Un run réel sur une copie de 15-20 pages a coûté ~$8 avec Claude Opus 4.7 exclusif. L'analyse comparative a montré que chaque tâche a un provider optimal différent.

**Répartition finale :**

| Tâche | Provider | Modèle | Justification clé |
|---|---|---|---|
| Transcription | Google Gemini | gemini-2.0-flash | Vision native, tier gratuit 1M tok/j |
| Correction | DeepSeek | deepseek-chat (V3) | MATH-500 ~90%, 18× moins cher qu'Opus |
| Diagnostic | DeepSeek | deepseek-reasoner (R1) | Modèle de raisonnement, causes cachées |
| Remédiation | Mistral | mistral-small-latest | Français académique natif |
| Extraction structurée | Claude | claude-sonnet-4-6 | tool_use forcé, fiabilité JSON |

**Routing :** automatique selon clés API disponibles dans `.env` — fallback Claude si clé absente.

**Analyse complète :** [docs/ai_providers_analysis.md](ai_providers_analysis.md)

**Coût résultant :** ~$0.02/copie vs ~$8.00/copie initial — réduction ×400.

---

### D-CEO-04 — Couche d'instructions expert (optionnelle)
**Décision :** Ajout d'une **couche optionnelle d'instructions expert** injectée dans le prompt de correction.

**Fonctionnement :** Avant de lancer la correction, l'enseignant peut saisir des instructions contextuelles propres au devoir : attentes spécifiques, points de vigilance, critères d'interprétation. Ces instructions sont injectées dans le prompt système de l'IA pour affiner la correction.

**Tolérance :** La tolérance d'erreur cible est volontairement ambitieuse (proche de ±0 pt) grâce à cette couche contextuelle. L'objectif est que l'IA produise une correction de très haute qualité lorsque les instructions expert sont fournies.

**Cette couche est optionnelle :** sans instructions, la correction reste basée uniquement sur l'énoncé et le barème.

---

### D-CEO-05 — Validation humaine
**Décision :** La **validation humaine est supprimée du pipeline applicatif**.

**Justification :** Elle se fait hors plateforme, par l'enseignant directement sur le rapport généré. Le système ne bloque plus la restitution en attente d'une validation dans l'interface.

**Conséquence :** Le flag `requires_teacher_review` reste présent dans les données JSON (information utile), mais aucun écran de validation n'est intégré dans le flux.

---

### D-CEO-06 — Format du rapport PDF
**Décision :** Contenu minimal du rapport :

- Note totale et détail par question (avec sous-questions)
- Commentaire pédagogique par question
- Zones marquées "Révision requise" (si confiance IA faible)
- Diagnostic des compétences maîtrisées / lacunes
- Plan de remédiation élève
- Score de confiance IA visible
- Logo Hakili Lab
- Numéro d'anonymisation de l'élève (pas de nom)

**Mode d'affichage :** Le contenu du rapport est d'abord affiché directement dans l'interface Streamlit. Un bouton "Télécharger le PDF" permet ensuite d'exporter le rapport.

---

### D-CEO-07 — Politique d'identification *(anonymisation supprimée)*
**Décision :** **Suppression de l'anonymisation.** Les copies sont identifiées par le nom réel de l'élève.

**Processus :**
1. L'enseignant saisit le nom de l'élève (copie unique) ou le fichier est nommé avec le nom de l'élève (batch).
2. Un identifiant technique sûr (slug, ex. `aminata_sawadogo`) est dérivé du nom pour les dossiers et fichiers.
3. Le PDF exporté affiche le nom réel de l'élève.
4. Aucune fiche de correspondance n'est générée.

**Justification :** La correction est un acte pédagogique interne — l'anonymisation compliquait le flux sans apporter de valeur dans le contexte d'utilisation réel.

---

### D-CEO-08 — Ressources internes pour la remédiation
**Décision :** Reporté — remédiation **générique** pour le MVP. L'IA suggère des thèmes et types d'exercices sans pointer vers une base de ressources. Option B (librairie Hakili) réservée à une version ultérieure.

---

### D-CEO-09 — Deux modes d'interface
**Décision :** L'interface Streamlit propose **deux modes distincts** :

| Mode | Description |
|---|---|
| **Copie Unique** | Traitement et correction d'une seule copie, résultat immédiat |
| **Batch** | Traitement d'un lot de copies (plusieurs élèves en une session), rapport consolidé |

Les deux modes partagent le même pipeline. Le mode Batch ajoute une boucle d'itération et une synthèse de classe (distribution des notes, compétences globales).

---

### D-CEO-10 — Format d'entrée optimal *(nouveau 2026-06-05)*
**Décision :** **PDF multi-pages scanné à 150 DPI, mode niveaux de gris.**

> **DPI** (*Dots Per Inch*) : nombre de pixels capturés par pouce (2,54 cm) de document physique. Un scan A4 à 150 DPI produit une image de 1 240 × 1 754 pixels, suffisant pour lire exposants et barres de fraction. À 300 DPI, l'image est 4× plus lourde sans gain de qualité pour un LLM.

**Justification :**
- 150 DPI satisfait le critère de Nyquist pour les traits manuscrits (≥ 2× la fréquence des éléments les plus fins)
- Scanner = distorsion perspective nulle (θ = 0°) vs photo téléphone (θ = 20-35° → 13% compression)
- Niveaux de gris : conserve les demi-tons (traits pâles) contrairement au N&B pur
- 300 DPI = overkill : +80% de tokens sans gain perceptible pour un LLM

**Matériel recommandé :**
- Usage régulier : Scanner ADF (ex. Epson WorkForce ES-65W, ~$130)
- Terrain : Smartphone + Microsoft Lens (mode Document → correction perspective automatique)

**Analyse complète :** [docs/input_pipeline_analysis.md](input_pipeline_analysis.md)

---

### D-CEO-11 — Coût cible et volume de référence *(nouveau 2026-06-05)*
**Décision :** Coût cible en production validé : **~$0.02/copie (avec Gemini), ~$12/an pour 540 copies.**

**Hypothèse de référence :**
- Volume : 3 classes × 6 évaluations × 30 élèves = 540 copies/an
- Pages/copie : ~11 pages (constaté sur copie réelle, 150 DPI)
- Total pages : ~5 940 pages/an → 33 pages/jour scolaire (Gemini tier gratuit : 1M tok/j)

**Coût réel mesuré par scénario (11 pages, 150 DPI) :**

| Scénario | Transcription | Correction | Diagnostic | Remédiation | **Total/copie** | **Total 100 copies** |
|---|---|---|---|---|---|---|
| Optimal (Gemini actif) | Gemini Flash ~$0.008 | DeepSeek V3 | DeepSeek R1 | Mistral | **~$0.028** | ~$2.80 |
| Actuel (Gemini KO, région) | Sonnet 4.6 ~$0.27 | DeepSeek V3 | DeepSeek R1 | Mistral | **~$0.29** | ~$29 |
| Fallback total (Claude seul) | Sonnet 4.6 ~$0.27 | Sonnet 4.6 | Haiku 4.5 | Sonnet 4.6 | **~$0.48** | ~$48 |

**Poste dominant : la transcription (vision).** Elle représente 93% du coût actuel parce que Claude Sonnet traite les images à $3/M tokens vs $0.10/M pour Gemini Flash. Réactiver Gemini réduirait le coût par 10.

**Seuil d'alerte :** si le volume dépasse 200 copies/jour avec Gemini actif, passer au tier payant (~$2/an supplémentaires).

---

### D-CEO-12 — Diagnostic ancré sur le programme officiel (RAG) *(nouveau 2026-06-08)*
**Décision :** Implémenter un système **RAG (Retrieval-Augmented Generation)** basé sur les curricula officiels du Burkina Faso pour le secondaire (6e → 3e).

**Architecture RAG :**
1. **Base de connaissance** (`data/knowledge/curriculum_*.yaml`) — 121 leçons structurées par classe, domaine, chapitre et leçon, avec `savoir`, `savoir_faire[]`, `prerequis_ids[]`, `mots_cles[]`, `erreurs_frequentes[]`
2. **Barèmes enrichis** (`data/knowledge/bareme_test_*.yaml`) — chaque question du test est mappée à ses `chunk_ids` de curriculum
3. **Retrieval** (`src/knowledge/curriculum_retriever.py`) — à la fin de la correction, les chunks associés aux questions échouées sont récupérés et injectés dans le prompt diagnostic via `{{CURRICULUM_CONTEXT}}`
4. **Sortie structurée** — `DiagnosticResult.competency_gaps: list[CompetencyGap]` avec chunk_id, classe, domaine, leçon, savoir_faire, erreurs_fréquentes

**Justification :** Un diagnostic qui dit "lacune en algèbre" est inutilisable. Un diagnostic qui dit "l'élève ne maîtrise pas `[4e_NUM_Ch4_L3] Identités remarquables` — erreur fréquente : (a+b)² = a²+b² (oubli de 2ab)" est actionnable par l'enseignant et valorisable auprès des parents.

**Couverture actuelle :** 6e, 5e, 4e, 3e. Le primaire (CE1–CM2, pertinent pour le test 6e) n'a pas encore de chunks — le diagnostic reste valide mais sans références de leçons spécifiques.

**Backward-compatible :** `get_diagnostic_context()` retourne `""` si `bareme_id` absent ou si aucune question échouée → le pipeline tourne sans RAG sans modification.

---

### D-CEO-13 — Tests Hakili pré-chargés (TestRegistry) *(nouveau 2026-06-08)*
**Décision :** Créer un **catalogue de tests standards Hakili** (`src/knowledge/test_registry.py`) qui auto-charge l'énoncé et le barème de chaque test standard au démarrage de la session.

**Flux enseignant avec TestRegistry :**
1. L'enseignant sélectionne "Test d'entrée en 3e" dans le menu déroulant
2. Un bandeau confirme : `✓ Énoncé pré-chargé (3 777 car.) · ✓ Barème 33 questions · ✓ RAG activé`
3. L'enseignant charge **uniquement la copie de l'élève** (PDF ou photos)
4. Aucun upload d'énoncé ni de barème n'est demandé

**Tests disponibles (v1) :**

| ID | Label | DOCX source | Barème YAML | Questions |
|---|---|---|---|---|
| `hakili_3e_v1` | Test d'entrée en 3e | `Hakilisso test de niveau 3e.docx` | `bareme_test_3e.yaml` | 33 (NUM + GEO) |
| `hakili_6e_v1` | Test d'entrée en 6e | `TEST DE NIVEAU,6eme,GROUPE 1.docx` | `bareme_test_6e.yaml` | 33 (NUM + GEO) |

**Justification :** Éliminer la friction opérationnelle (upload énoncé + saisie barème à chaque copie) est critique pour que l'outil soit utilisé quotidiennement par les enseignants Hakili sans formation.

**Extension :** Ajouter un test = ajouter une entrée dans `_TEST_CATALOG` + un DOCX dans `data/Documents/` + un YAML dans `data/knowledge/`. Aucune modification du code pipeline nécessaire.

---

### D-CEO-14 — Interface premium et positionnement marketing *(nouveau 2026-06-08)*
**Décision :** L'interface doit refléter le positionnement premium de Hakili Lab et fonctionner comme **instrument marketing** auprès des parents d'élèves.

**Implémentation (`src/ui/progress.py`) :**
- **Écran "Analyse en cours"** (remplace le spinner Streamlit générique) avec 7 étapes nommées, barre de progression temps réel (%, transition CSS cubic-bezier), logo Hakili animé (pulsation avec lueur)
- **Palette identitaire** : `#001e4a` (bleu marine), `#4a90e2` (bleu Hakili), `#27ae60` (vert validation)
- **Langage** : "Correction intelligente — ensemble voting", "Diagnostic pédagogique approfondi", "Génération du plan de remédiation" — vocabulaire expert qui justifie la valeur
- **Validation** : bandeau vert "✓ Analyse complète — rapport disponible" à la fin

**Étapes visibles (7) :**

| Étape | Label affiché | % déclenchement |
|---|---|---|
| ingestion | Ingestion & contrôle qualité image | 8% |
| transcription | Transcription multimodale (manuscrit) | 28% |
| correction | Correction intelligente — ensemble voting | 55% |
| rag | Récupération du contexte programme | 68% |
| diagnostic | Diagnostic pédagogique approfondi | 80% |
| remediation | Génération du plan de remédiation | 90% |
| export | Export PDF & rapport JSON | 98% |

**Modèle commercial visé :** Outil interne Hakili Lab pour les enseignants. Le rapport PDF + sujet de remédiation constituent le livrable.

**Justification :** Un outil qui produit un "spinner" générique n'est pas facturable. Un outil qui montre en temps réel une "Transcription multimodale" puis un "Diagnostic pédagogique approfondi" ancré sur le programme officiel justifie un prix premium.

---

### D-CEO-16 — Réorientation vers la correction assistée par IA *(nouveau 2026-06-11)*
**Décision :** Le système passe d'une **correction automatique** à une **correction assistée** où l'IA propose et l'enseignant valide.

**Ancien mode :** L'IA corrige, génère un rapport, l'enseignant le consulte hors système.
**Nouveau mode :** L'IA propose une note par question → l'enseignant accepte ou refuse dans l'interface → le score final est calculé en priorisant les décisions enseignant.

**Justification :**
- La correction automatique sans validation est inacceptable pour un document officiel
- L'enseignant doit rester le garant pédagogique — l'IA est un assistant, pas un décideur
- La validation in-app est plus rapide et traçable que la révision hors plateforme
- Elle ouvre la voie à l'amélioration continue du système (on mesure les désaccords IA/enseignant)

**Impact sur le pipeline :**
- Le pipeline se scinde en Phase A (correction IA + validation enseignant) et Phase B (diagnostic)
- `QuestionGrade` est enrichi : `teacher_decision` (accepted/refused/pending) + `teacher_score`
- `CopyGrade` est enrichi : `final_score` (basé sur les décisions enseignant)
- Le diagnostic (Phase B) ne se déclenche qu'après la validation complète de la Phase A

---

### D-CEO-17 — Le diagnostic approfondi comme objectif central *(nouveau 2026-06-11)*
**Décision :** Le **diagnostic pédagogique approfondi** est positionné comme la **valeur principale** du produit — pas la correction.

**Ce que produit le diagnostic :**
- Pour chaque question échouée : identification des causes cachées (pas des symptômes)
- Ancrage sur une leçon précise du programme officiel (chunk_id)
- Identification de la classe concernée (la lacune vient de quelle année ?)
- Exemples concrets de l'erreur type pour chaque lacune (depuis `erreurs_frequentes` du curriculum)
- Le tout organisé par domaine (numérique / géométrique)

**Ce que le diagnostic ne fait plus :**
- Lister des commentaires par question (supprimé du rapport)
- Produire une note (rôle de la Phase A)

**Structure du rapport final :**
1. Tableau bonnes réponses (N° question · points)
2. Tableau mauvaises réponses (N° question · 0/points)
3. Corps : diagnostic approfondi par domaine + plan de remédiation ciblé

**Justification :** Un enseignant peut corriger une copie manuellement. Ce qu'il ne peut pas faire facilement : identifier que "la confusion entre (a+b)² et a²+b²" vient d'une lacune de 4e non comblée, ni produire 5 exercices ciblés sur cette lacune en 2 minutes. C'est là la valeur différenciante.

---

### D-CEO-15 — Migration génération PDF vers XeLaTeX *(nouveau 2026-06-11)*
**Décision :** Remplacer ReportLab par **XeLaTeX + Jinja2** pour la génération des rapports PDF.

**Contexte :** ReportLab impose un layouting manuel (coordonnées pixel par pixel) qui rendait les rapports structurellement rigides et visuellement basiques. Les formules mathématiques et tableaux étaient difficiles à rendre proprement.

**Architecture mise en place :**
- `src/pipeline/pdf_report_latex.py` — rapport de correction (note, commentaires, diagnostic, compétences)
- `src/pipeline/pdf_remediation_latex.py` — sujet de remédiation élève
- `templates/` — templates Jinja2 `.tex` avec commandes LaTeX custom (`\skillbadge`, etc.)
- Fonction `_le()` — escape automatique des caractères spéciaux LaTeX dans les données élèves
- **Fallback automatique ReportLab** si `xelatex` n'est pas installé sur la machine

**Avantages :**
- Rendu typographique professionnel (formules mathématiques natives, tableaux, mise en page)
- Facilité de modification du template sans toucher au code Python
- Compatible avec le positionnement premium de l'outil auprès des parents

**Fichiers supprimés :**
- `src/pipeline/pdf_report.py` (ReportLab)
- `src/pipeline/image_quality.py` (contrôle qualité image standalone — logique intégrée dans l'ingestion)

**Prérequis :** TeX Live ou MiKTeX installé sur la machine de l'enseignant (optionnel — le fallback ReportLab garantit que le pipeline ne bloque pas si xelatex est absent).

---

### D-CEO-18 — Portail de consultation Neon Postgres *(nouveau 2026-07-09)*
**Décision :** Ajout d'une couche de persistance PostgreSQL (Neon) — tables `centre`, `eleve`, `copie`, `document`, `utilisateur` (rôles admin / responsable_centre / enseignant) — et d'un portail de consultation Streamlit (login + historique élève + recherche par rôle).

**Statut : scaffolding uniquement.** Ce qui existe : modèles SQLAlchemy (`src/db/models.py`), connexion + migrations Alembic (`migrations/`), services CRUD (`src/services/`), pages Streamlit protégées par login (`src/ui/pages/`), intégrées nativement dans l'app existante (`src/ui/app.py` reste inchangé — Streamlit détecte `src/ui/pages/` automatiquement).

**Ce qui n'est PAS encore fait (dette explicite) :**
- Le pipeline de correction (`src/pipeline/pipeline.py`) n'écrit **rien** dans ces tables — aucune copie n'est persistée automatiquement après une correction. Câblage différé à une tâche ultérieure.
- Aucun compte admin n'est pré-créé — la table `utilisateur` est vide après migration ; le premier compte doit être inséré manuellement via `create_utilisateur()`.
- Les fichiers (scans, rapports, remédiations) sont stockés en `BYTEA` directement en base (v1) — connu comme un anti-pattern à moyen terme (stockage objet à envisager si le volume grossit), accepté pour le prototype.

**Tension avec D004** ("Stockage local pour prototype") : D004 concernait le pipeline de correction (JSON/PDF en local, `runs/`), qui reste inchangé. D-CEO-18 ouvre une persistance cloud parallèle pour un besoin différent (consultation multi-centres/multi-rôles), sans remplacer D004 tant que le câblage pipeline n'est pas fait.

**Sécurité :** mots de passe hashés en PBKDF2-HMAC-SHA256 salé (stdlib, 600k itérations) — pas de dépendance externe ajoutée. La connection string Neon vit uniquement dans `.env` (jamais dans un fichier versionné).

---

### D-CEO-19 — Câblage du pipeline sur la persistance Neon *(nouveau 2026-07-15)*
**Décision :** Acte les évolutions réelles depuis D-CEO-18 — celui-ci reste tel quel comme enregistrement daté de l'état du 2026-07-09 ; les points ci-dessous en sont la suite, pas une réécriture.

**Navigation :** `src/ui/pages/` (pages Streamlit multi-fichiers protégées par login) abandonné. `src/ui/app.py` porte désormais toute la navigation via un menu interne (radio dans la sidebar, branchement par variable `page`). `src/ui/auth.py` (`require_login`, `render_logout_button`), écrit pour l'ancien modèle par pages, n'était plus importé nulle part — supprimé.

**Pipeline branché sur la base (dette D-CEO-18 comblée) :** `src/pipeline/pipeline.py` écrit désormais en base à 5 points d'injection, tous best-effort (n'échouent jamais le pipeline, journalisés `[DB OK]` / `[DB WARNING]`) :
1. Réception de la copie — création Élève + Copie (placeholder) + document `scan`
2. Rapport de correction généré — document `rapport`
3. Sujet de remédiation généré — document `remediation`
4. Note finale — écrite en provisoire (4a, avant validation enseignant) puis en définitive (4b, après validation, écrase 4a)
5. Classe réelle — extraite de l'en-tête transcrit (`EVALUATION {classe}`, `src/core/classe_normalizer.py`) et écrasant le placeholder posé au point 1 ; jamais devinée, laissée en placeholder si l'extraction échoue

**Rattrapage des copies déjà en base :** `backfill_classe.py` et `backfill_notes.py` (scripts ponctuels, non intégrés au pipeline) ont corrigé les copies écrites avant le câblage des points 4 et 5, à partir de `runs/<copy_id>/result.json` déjà sur disque — même logique d'extraction que le pipeline, aucune valeur devinée en cas d'échec.

**Comptes utilisateurs (dette D-CEO-18 comblée) :** `seed_users.py` (idempotent) crée admin + un responsable par centre + enseignants de test. `create_admin.py` (non idempotent, faisait doublon) supprimé.

**Robustesse Neon :** `pool_pre_ping=True` et `pool_recycle=300` ajoutés à `create_engine` (`src/db/database.py`). Neon (pooler PgBouncer) met la base en veille après inactivité ; les connexions gardées dans le pool SQLAlchemy devenaient mortes sans le savoir, provoquant des écritures silencieusement perdues. `pool_pre_ping` teste chaque connexion avant usage et la remplace si morte ; `pool_recycle` évite de garder des connexions que Neon aura de toute façon fermées. Le retry tenacity existant reste en complément pour les erreurs réseau transitoires.

**`annee_scolaire` :** abandonnée comme clé d'affichage de l'évolution d'un élève — l'onglet Comparaison est désormais strictement chronologique (tri sur `date_soumission`), motivé par le fonctionnement réel d'un centre d'appui (tests continus toute l'année, le découpage en années scolaires n'a pas de sens). La colonne reste en base et continue d'être alimentée par le pipeline (`datetime.now().year`) — elle peut resservir, seul son usage pour le regroupement/tri en UI a été retiré.

**Logs :** `TimedRotatingFileHandler` ajouté (`logs/`, rotation quotidienne à minuit, 30 jours conservés) en complément de la sortie console existante, pour que les avertissements d'écriture base (`[DB WARNING]`) survivent à la fermeture du terminal. `logs/` ajouté au `.gitignore` (données personnelles potentielles — noms d'élèves dans les messages de log).

---

### D-CEO-20 — Élèves et profs migrés vers Google Sheets, table ELEVE supprimée *(nouveau 2026-07-17)*
**Décision :** Les élèves et les profs ne vivent plus dans PostgreSQL mais dans deux Google Sheets distincts, contrôlés par un tiers (le docteur). PostgreSQL ne garde plus que ce qui concerne la correction elle-même : `identifiant_hakili` (texte, calculé depuis les Sheets), les documents (scan/rapport/remédiation) et les notes. Fondation de lecture posée d'abord (`src/integrations/google_sheets.py`, D-CEO-19 et suivants), câblage du pipeline et démolition de l'ancien modèle actés ici.

**Schéma :** table `eleve` supprimée. `copie.eleve_id` (UUID, FK vers `eleve.id`) remplacé par `copie.identifiant_hakili` (texte). Migration `25898695d3c4` (« supprime table eleve, copie.eleve_id devient identifiant_hakili »). Corrigé au passage : le `downgrade()` de la migration initiale (`3eee6db8ae6e`) ne supprimait pas le type ENUM Postgres `userrole`, ce qui cassait la procédure `alembic downgrade base` puis `alembic upgrade head` (« type userrole already exists ») — ajout du drop du type ENUM dans son downgrade.

**Élève choisi explicitement, jamais deviné :** en mode Copie unique, l'enseignant sélectionne l'élève dans une liste déroulante alimentée par `get_eleves()` (nom, prénom, classe, centre — jamais `contact_parents`), affichée à gauche du choix de test. En mode batch, une sélection manuelle par fichier n'a pas de sens pour 30 copies d'un coup : le nom du fichier (convention déjà en place, nom+prénom de l'élève) est mis en correspondance avec le roster Sheets (comparaison repliée, insensible aux accents/casse) ; sans correspondance unique, cette copie précise est bloquée et journalisée, le reste du lot continue.

**Blocage avant tout appel IA :** `_db_persist_scan` (point d'injection 1) vérifie l'existence de l'élève via `get_eleve_by_identifiant` en tout premier — avant la construction des clients IA. Élève introuvable → exception, aucun appel IA, `[DB WARNING]` journalisé. C'est la seule étape non best-effort du pipeline ; l'écriture en base une fois l'élève confirmé reste best-effort comme les autres points d'injection.

**Décision classe — Sheet comme repli, extraction toujours souveraine :** `Copie.classe` continue d'être déterminée par l'extraction de l'en-tête transcrit (`EVALUATION {classe}`, inchangée depuis D-CEO-19) — pas par la colonne `classe` du Sheet. Motif : `Copie.classe` est un fait par copie (quelle classe au moment de CET examen), alors que la colonne du Sheet est le statut administratif COURANT de l'élève (peut changer en cours d'année — `reprend_la_classe`) ; l'utiliser comme source écraserait la variation historique dont dépend l'onglet Comparaison (détection de changement de classe entre deux copies). En revanche, la classe du Sheet sert désormais de **valeur initiale** au point d'injection 1 (remplace le placeholder générique "Non renseignée" par une vraie info déjà connue), toujours écrasée au point 5 si l'extraction donne un résultat fiable et différent.

**Suppressions (plus de source, plus de raison d'être) :**
- `src/services/eleve_service.py` — fichier entier supprimé : chaque fonction (`get_or_create_eleve`, `get_eleve_by_identifiant`, `get_eleves_by_centre*`, `update_eleve_date_naissance`, `preview_eleve_upsert`, `upsert_eleve_from_import`...) manipulait la table `eleve`. `get_historique_eleve` déplacée dans `copie_service.py`, adaptée pour filtrer par `identifiant_hakili`.
- Vues Admin « Ajouter élève », « Importer Excel », « Compléter profil élève » et la recherche/suppression d'élève — toutes du CRUD sur une table qui n'existe plus (créer/modifier un élève se fait désormais dans le Sheet, hors de cette application). L'onglet Admin ne garde que Statistiques.
- `backfill_classe.py`, `backfill_notes.py` — scripts de rattrapage ponctuels pour des copies écrites avant le câblage des points 4/5 (bug déjà résolu) ; la base étant vidée pour ce chantier, il n'y a plus de copie historique à rattraper.
- `create_admin.py` déjà supprimé en D-CEO-19 ; `init_centres.py` et `seed_users.py` conservés (Centre/Utilisateur inchangés, hors périmètre login).

**Suivi (Historique / Tableau des élèves / Comparaison) adapté a minima :** `get_accessible_eleves`/`can_access_eleve` (`user_service.py`) lisent désormais `get_eleves()` (Sheets) et filtrent par centre/classe de l'utilisateur au lieu de requêter `eleve`/`eleve_id` ; `afficher_historique` et `_render_comparaison_view` acceptent un dict Sheets au lieu d'un objet `Eleve`. Refonte visuelle de ces vues non traitée ici (prévue plus tard).

---

### D-CEO-21 — Login branché sur le Sheet profs, table UTILISATEUR supprimée *(nouveau 2026-07-17)*
**Décision :** Suite directe de D-CEO-20 côté profs — les comptes (admin, responsables, enseignants) ne vivent plus dans PostgreSQL mais dans le Sheet profs (email, nom, prénom, role, centre, classe), en lecture seule pour l'application. **Le Sheet fait foi pour le droit d'accès, à chaque connexion** : un email retiré du Sheet perd l'accès même s'il a toujours un mot de passe en base. Nom, rôle, centre, classe ne sont plus jamais écrits en base — uniquement en session, relus depuis le Sheet à chaque login.

**Stockage du mot de passe — table dédiée `credentials` (option retenue plutôt que réduire `utilisateur`) :** `email` (clé primaire) + `password_hash` + `date_creation`, aucune autre colonne. Retenu plutôt que de garder `utilisateur` amputée de ses colonnes d'identité : le nom `utilisateur` continue d'évoquer une identité complète, ce qui inviterait quelqu'un à y recoller un jour nom/rôle/centre par habitude et à recréer le second point de vérité qu'on cherche justement à éliminer. `credentials` nomme sans ambiguïté ce qui reste : un mot de passe attaché à un email, rien d'autre.

**Schéma :** tables `utilisateur` et `centre` supprimées, table `credentials` créée. Migration `d919411e7423`. Même piège ENUM Postgres que D-CEO-20 (`userrole` non nettoyé par un simple `drop_table`) — corrigé dans cette migration ; cycle complet `alembic downgrade base` → `alembic upgrade head` sur les 3 migrations retesté et validé.

**`centre` supprimée aussi :** vérifié qu'aucune table ne la référence plus après le retrait de `utilisateur.centre_id` (`Copie` n'a jamais référencé `Centre`). Les noms de centre vivent dans la colonne `centre` des Sheets (élèves et profs) — une table `Centre` séparée en base serait redevenue un second point de vérité. Décision prise après vérification explicite des dépendances, signalée ici en toute transparence : à objecter si une dépendance future y était prévue.

**`UserRole` (enum Python, `src/db/models.py`) :** n'est plus le type d'une colonne SQL — gardé comme enum de confort pour comparer proprement le profil choisi au login. Valeurs alignées sur le vocabulaire réel du Sheet (`administrateur`, `responsable`, `enseignant`) plutôt que sur les anciennes valeurs internes (`admin`, `responsable_centre`), pour éviter une table de correspondance supplémentaire qui pourrait diverger.

**`src/services/auth_service.py` (nouveau) :** `authentifier(db, profil_choisi, email, mot_de_passe=None)` — lit le Sheet d'abord (existence + rôle), ne regarde le mot de passe qu'ensuite ; retourne un statut explicite (`email_absent` / `role_mismatch` / `creation_requise` / `mot_de_passe_incorrect` / `ok`). `creer_mot_de_passe(...)` re-vérifie le Sheet avant d'écrire, jamais de création "à l'aveugle". `hash_password`/`_verify_hash` (PBKDF2-HMAC-SHA256, 600k itérations) déplacés depuis `user_service.py`, logique inchangée.

**Suppressions :** `create_utilisateur` (déjà retiré en D-CEO-19) ; `get_utilisateur_by_email`, `get_utilisateur_by_id`, `verify_password` (`user_service.py`) — leur table n'existe plus. `seed_users.py` et `init_centres.py` supprimés (créaient des lignes dans des tables qui n'existent plus) — mise à jour de ce qui était noté conservé en D-CEO-20.

**`get_accessible_eleves`/`can_access_eleve` adaptées :** prennent désormais un dict Sheet (avec un champ `role_enum` ajouté en session au login) au lieu d'un objet `Utilisateur` ; comparent `centre`/`classe` en texte directement (Sheet à Sheet), sans plus jamais résoudre via une table `Centre`.

**Vérifié en conditions réelles** (Sheet profs réel, `resp.tampouy@hakili.com`) : première connexion → création de mot de passe → reconnexion avec bon mot de passe → OK ; mauvais mot de passe → refusé ; bon email/mauvais profil choisi (enseignant Tampouy essayant "Responsable") → refusé ; email absent du Sheet → refusé ; email avec mot de passe en base mais absent du Sheet (simulé) → refusé, confirmant la règle « le Sheet fait foi ». `get_accessible_eleves`/`can_access_eleve` retestées avec le nouveau format de session : mêmes résultats qu'en D-CEO-20 (admin 12, responsable Tampouy 4, enseignant 3e Tampouy 2).

---

### D-CEO-22 — Liste de centres autorisée + détection des divergences Sheets *(nouveau 2026-07-17)*
**Décision :** Depuis la suppression de la table CENTRE (D-CEO-21), les noms de centre ne sont plus que du texte libre dans la colonne `centre` des deux Sheets (élèves, profs), potentiellement saisis par des personnes différentes — une faute de frappe dans l'un des deux casse silencieusement le lien de permission (comparaison texte à texte). On introduit une liste officielle et une vérification systématique à la lecture.

**Emplacement de la liste — nouveau module `src/core/centre_normalizer.py`, pas `config.py` :** le projet a déjà un précédent directement comparable pour ce genre de donnée (`CANONICAL_CLASSES` dans `src/core/classe_normalizer.py` — une petite liste canonique métier, pas un réglage d'environnement). `config.py`/`.env` sont réservés aux clés API, URLs et chemins qui varient par déploiement ; la liste des 4 centres Hakili Lab n'est pas de cette nature, elle est stable et partagée par tout le monde. Suivre le précédent déjà établi plutôt qu'ouvrir un second pattern pour un besoin identique. Ajouter un centre = modifier `CENTRES_AUTORISES` dans ce seul fichier, rien d'ailleurs à toucher.

**Normalisation anodine (`fold_centre`) :** minuscule, sans accents, espaces réduits — strictement l'esprit de `classe_normalizer._fold`, sans jamais toucher aux lettres elles-mêmes. `" tampouy "` / `"TAMPOUY"` → `"Tampouy"` (reconnu), mais `"Tampuy"` (vraie faute) reste `"Tampuy"` (non reconnu) puisque la lettre manquante change la forme repliée. Vérifié en conditions réelles avec `hashlib`-style tests directs sur les 5 cas (centre correct, variation espaces, variation casse, vraie faute, centre vide) : comportement exact dans les 5 cas.

**Comportement retenu pour un centre non reconnu — ligne conservée, pas rejetée :** `_verifier_et_normaliser_centre` (`google_sheets.py`) journalise `[SHEETS WARNING]` (ligne, Sheet, valeur brute, liste autorisée) mais garde la ligne avec le centre tel quel plutôt que de la jeter ou de deviner un centre. Motif : faire disparaître silencieusement un élève ou un prof à cause d'une faute de frappe serait pire que le problème lui-même — l'alerte suffit à signaler au docteur qu'il faut corriger le Sheet, sans perdre la ligne en attendant. Un centre vide (ex. l'admin, qui n'en a pas) n'est pas une alerte — cas légitime distinct d'un centre erroné.

**Centres reconnus normalisés en place, à la source :** une variation anodine reconnue est remplacée par sa forme canonique directement dans le dict retourné par `get_eleves()`/`get_profs()` — tout le reste du code voit ensuite des valeurs déjà propres, sans repasser par une normalisation à chaque comparaison.

**Cohérence lecture ↔ permissions :** `get_accessible_eleves`/`can_access_eleve` (`user_service.py`) comparent désormais via `centres_correspondent()` (même module), pas une égalité texte nue — défense en profondeur : même si la centralisation à la lecture suffirait en théorie, la comparaison elle-même tolère aussi casse/accents/espaces sans jamais faire correspondre deux fautes différentes entre elles (repli sur égalité texte stricte si l'un des deux centres n'est pas reconnu).

**UI — Statistiques (Admin) :** avertissement `st.warning` si un centre non reconnu apparaît dans les données chargées (« Attention : centre(s) non reconnu(s)... »), en plus des logs — ne passe pas inaperçu même sans consulter les logs.

**Vérifié en conditions réelles** (Sheets fictifs réels) : les 4 centres actuels (Siao, Saaba, Nagrin, Tampouy) chargent sans aucune alerte, forme canonique confirmée des deux côtés (élèves et profs). `get_accessible_eleves`/`can_access_eleve` retestées avec un centre de session délibérément sale (`" TAMPOUY "`) : toujours 4/2 élèves accessibles comme attendu, `can_access_eleve` toujours `True` malgré la casse — et toujours `False` pour un responsable d'un autre centre (Siao face à un élève de Tampouy). Test direct de `_verifier_et_normaliser_centre` sur les 5 cas (correct / espaces / casse / vraie faute / vide) : résultat exact dans chaque cas, alerte journalisée uniquement pour la vraie faute.

---

### D-CEO-23 — Vue de suivi Responsable avec code couleur de tendance *(nouveau 2026-07-18)*
**Décision :** Un responsable de centre voit désormais ses élèves (déjà filtrés par centre via `get_accessible_eleves`) avec une pastille reflétant leur PROGRESSION dans le temps, pas une photo figée de la dernière note — comparaison des deux dernières copies notées.

**Règle de tendance :** écart entre les deux dernières notes (copies avec `notes_finales` non NULL, triées par `date_soumission`) : `>= +1` progresse (vert), entre -1 et +1 exclu stagne (orange), `<= -1` régresse (rouge). Moins de 2 copies notées → « insuffisant » (gris, « pas assez de données ») — l'élève reste affiché, jamais caché.

**Seuil configurable — nouveau module `src/core/tendance.py`, pas `config.py` :** même raisonnement qu'en D-CEO-22 pour `CENTRES_AUTORISES` — le projet a déjà deux précédents directs (`CANONICAL_CLASSES` dans `classe_normalizer.py`, `CENTRES_AUTORISES` dans `centre_normalizer.py`) pour une constante métier stable, éditable à un seul endroit, sans dépendre de l'environnement de déploiement. `SEUIL_TENDANCE = 1.0` vit dans ce module, à côté de la fonction pure `calculer_tendance()` qui l'utilise — cohérent avec le fait que `config.py` contient déjà `confidence_review_threshold` pour un besoin différent (réglage pipeline IA, pas règle d'affichage figée) ; les deux emplacements coexistent pour des raisons différentes, choix assumé et documenté ici plutôt que tranché en silence.

**Performance — chargement groupé, pas une requête par élève :** `get_copies_pour_identifiants(db, identifiants)` (`copie_service.py`) charge en une seule requête (`WHERE identifiant_hakili IN (...)`) les copies de tous les élèves du centre, puis regroupe en mémoire. Une requête par élève aurait fait N requêtes pour un centre à N élèves — inutile alors qu'une seule requête groupée suffit.

**Portée :** seule la vue Responsable change (`_render_tableau_responsable`, appelée dans "Tableau des élèves" uniquement si `role_enum == responsable_centre`). Admin et enseignant gardent exactement le tableau existant, inchangé — le rôle enseignant aura sa propre vue dédiée dans un chantier séparé (tableau-profil).

**Mise en avant des élèves en baisse :** tri (régresse d'abord, puis stagne, progresse, insuffisant) + compteur visible en haut (« N élève(s) en baisse »).

**Vérifié :** 10 tests unitaires sur `calculer_tendance` (`tests/test_tendance.py`) — progression nette, régression, stagnation, une seule copie, zéro copie, note NULL ignorée (y compris au milieu d'un historique plus long), bornes exactes du seuil, ordre d'entrée indifférent au tri : 10/10 passent. Vérification de bout en bout avec de vraies données Tampouy (4 élèves réels, copies de test créées puis supprimées) : KABRE Charles Eliel 10→13 progresse, KANAZOE Abdoul Hafiz 14→11 régresse, KANAZOE Rachidatou 12→12.5 stagne, ZONGO Ibrahim 0 copie → insuffisant mais bien présent dans la liste ; tri et compteur (« 1 élève en baisse ») corrects ; `contact_parents` jamais lu dans le chemin d'affichage.

---

### D-CEO-24 — Vue Enseignant : tableau-profil individuel d'un élève *(nouveau 2026-07-18)*
**Décision :** Complète D-CEO-23 côté enseignant — vue individuelle (un élève choisi dans une liste déroulante restreinte à son centre+classe) plutôt que la vue d'ensemble du responsable. `_render_profil_enseignant` branché dans "Tableau des élèves" (`sub_tab2`) uniquement si `role_enum == enseignant` ; admin et responsable gardent leur rendu exact, inchangé.

**Réutilisation, pas de duplication :** `calculer_tendance()` et `_TENDANCE_STYLE`/`SEUIL_TENDANCE` (D-CEO-23) appelés tels quels — même pastille, même seuil, aucune deuxième implémentation. `_afficher_documents_copie` (téléchargement + aperçu, déjà utilisée par l'onglet Historique) réutilisée verbatim pour les documents de chaque copie — l'aperçu PDF passe par `_doc_pdf_pages_png` déjà en place, pas de nouveau moteur de rendu.

**Bug trouvé et corrigé en vérifiant PARTIE 4 (sécurité) :** `can_access_eleve` pour un enseignant vérifiait l'existence d'une `Copie` en base avec la bonne classe — critère différent de `get_accessible_eleves`, qui filtre sur la classe déclarée dans le Sheet. Un élève sans copie soumise (donc listé par `get_accessible_eleves` via son rôle Sheet, mais sans aucune `Copie` en base) se voyait refuser l'accès à son propre profil par `can_access_eleve` — bloquant la fonctionnalité pour tout élève n'ayant pas encore de copie. Corrigé : `can_access_eleve` compare désormais `eleve.get("classe") == user.get("classe")` (Sheet), exactement le même critère que `get_accessible_eleves`. Ancien critère hérité de l'ère pré-Sheets, où la classe n'existait que sur `Copie` (`Eleve` n'avait pas de champ classe) — devenu incohérent depuis que l'identité vient des Sheets.

**Chargement des copies — une seule requête par profil, pas de N+1 :** `get_historique_eleve(db, identifiant)` appelée une seule fois par sélection d'élève, réutilisée à la fois pour la tendance, le résumé chiffré et la liste chronologique. `get_copies_pour_identifiants` (chargement groupé multi-élèves, D-CEO-23) non nécessaire ici : la vue ne traite jamais qu'UN élève à la fois, contrairement à la vue responsable qui balaie tout un centre.

**Vérifié en conditions réelles** (Sheet Tampouy réel + copies de test) : enseignant 3e Tampouy voit exactement 2 élèves (KABRE Charles Eliel, ZONGO Ibrahim), pas les autres classes/centres. Test de permission forcé : élève de la bonne classe → accès autorisé ; élève de la même école mais mauvaise classe (KANAZOE Abdoul Hafiz, 4e) → refusé ; élève d'un autre centre (Siao) → refusé. Profil complet vérifié sur KABRE Charles Eliel (3 copies test, dont une non notée) : tendance "progresse" (9.0→12.5) cohérente avec le même calcul que la vue responsable, résumé chiffré correct (3 copies, dernière note retrouvée rétroactivement, date de la dernière copie distincte de la date de la dernière note notée), chronologie ascendante correcte, copie non notée affichée "Non notée" sans être masquée. Aperçu PDF testé sur un vrai document stocké en base (rendu PNG réussi via `_doc_pdf_pages_png`). `contact_parents` absent de tout le chemin d'affichage (vérifié par grep). Données de test supprimées après vérification.

---

### D-CEO-25 — Connexion nom+PIN, personnel unifié, centres dérivés des Sheets *(nouveau 2026-07-20, corrigé 2026-07-20)*
**Décision :** Remplacement complet de la connexion email + mot de passe par une sélection du nom (liste déroulante recherchable) + code PIN à 4 chiffres, les deux lus dans le Sheet personnel à chaque connexion. Table `credentials` supprimée de PostgreSQL (migration `f8928cd01df9`) — PostgreSQL ne porte plus aucune donnée d'authentification, tout vit dans les Sheets. Le PIN est stocké EN CLAIR dans le Sheet (choix assumé du docteur, Sheet réservé, aucun anti-forçage demandé).

**Rôle et clé de regroupement :** le rôle (enseignant/responsable/administrateur) vient désormais d'une colonne "role" du Sheet personnel, plus du fichier d'origine — l'administrateur est une ligne du Sheet comme les autres, avec un PIN. Regroupement des lignes (une par affectation) par **(nom, prénom)** repliés au lieu de l'email, devenu peu fiable (colonne optionnelle, vide chez la quasi-totalité des enseignants réels). Limite assumée : deux vrais homonymes (même nom ET prénom) fusionneraient à tort leurs affectations — cas jugé assez rare pour être accepté, à signaler si observé en pratique.

**`ADMIN_EMAILS` rendu dormant, pas supprimé :** la liste blanche mise en place au chantier précédent (D-CEO-21 et suivants) n'est plus lue par `auth_service.py` — l'admin s'authentifie désormais comme tout le monde via le Sheet. Le champ `settings.admin_emails`/`admin_emails_list` reste défini en config (documenté comme dormant) : RECOMMANDATION faite au docteur de le garder comme accès de secours si les Sheets deviennent injoignables (aucun autre chemin de connexion n'existerait alors), ou de le retirer s'il est jugé inutile — décision non tranchée en silence, signalée explicitement ici et dans le rapport de chantier.

**Centres dérivés dynamiquement, plus de liste figée :** `CENTRES_AUTORISES` retirée de `centre_normalizer.py`. `deriver_centres()` construit désormais la liste des centres réels à partir de TOUTES les valeurs "centre" vues dans les Sheets (élèves + personnel), regroupées par forme repliée (casse/accents/espaces) ; la graphie la plus fréquente devient la forme canonique. Un centre vu `SEUIL_CENTRE_SUSPECT` (= 1) fois ou moins est signalé "suspect" (alerte discrète côté admin + log `[SHEETS WARNING]`) sans jamais être bloqué ni corrigé — le docteur ajoute un centre en l'écrivant simplement dans un Sheet, aucune modification de code. `centres_correspondent()` simplifiée en conséquence : comparaison directe des formes repliées, sans dépendre d'une liste.

**Colonnes optionnelles :** `_resoudre_colonnes`/`_fetch_sheet_rows` acceptent désormais un paramètre `optionnelles` — une colonne logique absente du Sheet (pas seulement vide) ne lève plus d'erreur si elle est listée comme optionnelle (`classe`, `email` pour le personnel). `role` et `pin`, eux, restent **obligatoires** : tant que le docteur n'a pas ajouté ces deux colonnes au Sheet personnel réel, `get_personnel()` lève une `GoogleSheetsError` claire (colonnes manquantes nommées + en-têtes trouvés) plutôt que de charger un personnel sans rôle ni PIN exploitable — comportement voulu, cohérent avec le reste du module (jamais de dégradation silencieuse sur une donnée structurante).

**UI :** écran de connexion simplifié (plus de radio "Profil", plus de flux "créer mon mot de passe") ; nouveau composant réutilisable `_selectbox_recherchable` (recherche + selectbox) appliqué à la connexion, à la sélection d'élève (traitement unique, vue enseignant) — recherche insensible à la casse/aux accents ET à l'ORDRE des mots (`_correspond_recherche`, bug trouvé et corrigé en vérifiant : une recherche "Nom Prénom" ne retrouvait pas un élève affiché "Prénom Nom"). Placeholders sans tirets cadratin. Vue "Personnel par centre" (admin) réécrite sur les centres dérivés, affiche tout le personnel y compris sans PIN (mention "PIN manquant" discrète) et y compris administrateur/rôles non reconnus (jamais masqué). Tableau élèves (admin) : colonnes École/Boursier/Redoublant ajoutées, colonne "Identifiant" (identifiant_hakili) retirée — jamais affiché à l'écran. Recherche nom/prénom ajoutée côté responsable (tri par tendance et compteur de baisse inchangés). Paragraphe obsolète ("la gestion des élèves se fait dans les Sheets...") retiré de l'onglet Administration.

**CORRECTION (même jour) — un seul Sheet personnel, pas deux :** les fichiers enseignants et responsables ont été fusionnés par le docteur en un unique Google Sheet. `GOOGLE_SHEET_ENSEIGNANTS_ID` et `GOOGLE_SHEET_RESPONSABLES_ID` remplacées par une seule variable `GOOGLE_SHEET_PERSONNEL_ID` (`config.py`, `.env.example`). `_load_personnel()`/`_centres_bruts_toutes_sources()` lisent désormais ce Sheet unique ; toute la logique de fusion/dédoublonnage entre deux Sheets (`_personnel_sheet_ids()`) a été retirée, devenue inutile. Le rôle continue de venir de la colonne "role" de chaque ligne, inchangé. **Le docteur doit mettre à jour son `.env` local** pour remplacer les deux anciennes variables par `GOOGLE_SHEET_PERSONNEL_ID=<identifiant du Sheet fusionné>` — sans cela, l'application ne démarre plus (Pydantic rejette les variables d'environnement inconnues).

**Vérifié :** 10 tests dans `tests/test_google_sheets.py` (regroupement nom+prénom multi-affectation, rôle depuis la colonne, personne sans PIN comptée mais chargée, colonnes optionnelles absentes sans crash, dérivation de centres avec convergence anodine + détection de centre suspect, et désormais un test dédié confirmant qu'enseignant/responsable/administrateur se chargent et se connectent tous les trois depuis le MÊME identifiant de Sheet) — 10/10 passent. Contre les vrais Sheets : élèves inchangés (84 chargés) ; personnel lève l'erreur claire attendue tant que les colonnes Role/PIN n'existent pas encore côté réel (le docteur doit les ajouter — c'est l'objet même de ce chantier). Scénarios simulés avec données réalistes : connexion PIN correct/incorrect, enseignant "Tle" voit TleD et TleC de son centre sans voir un autre centre, Pissy apparaît dans les centres dérivés via son seul enseignant (aucun élève), recherche responsable insensible à l'ordre des mots confirmée avec un vrai nom (SANOU Feryel, centre SIAO réel), aucune fuite de `identifiant_hakili`/`contact_parents` à l'écran, enseignant/responsable/admin authentifiés depuis un Sheet personnel unique simulé. App bootée en headless sur toutes les pages : aucun crash.

---

## Tableau de synthèse

| ID | Sujet | Décision finale | Date |
|---|---|---|---|
| D001 | Flux d'ingestion | Copie complète (pas exercice par exercice) | 2026-05-08 |
| D002 | Source de vérité | JSON → PDF | 2026-05-08 |
| D003 | Interface | Streamlit | 2026-05-08 |
| D004 | Stockage | Local pour prototype | 2026-05-08 |
| D005 | Volume cible | 100 copies réelles | 2026-05-08 |
| D-CEO-01 | Matières et niveaux | Mathématiques, **6e à la Terminale** | 2026-05-08 |
| D-CEO-02 | Format barème | Binaire 0/1 par question et sous-question | 2026-05-08 |
| D-CEO-03 | Stratégie IA | **Multi-provider** (Gemini + DeepSeek + Mistral + Claude) | **2026-06-05** |
| D-CEO-04 | Instructions expert | Couche optionnelle d'instructions contextuelles | 2026-05-08 |
| D-CEO-05 | Validation humaine | Hors plateforme (enseignant sur PDF exporté) | 2026-05-08 |
| D-CEO-06 | Rapport PDF | Note · commentaires · diagnostic · remédiation · confiance | 2026-05-08 |
| D-CEO-07 | Identification | Nom réel de l'élève (slug technique pour fichiers) | 2026-05-08 |
| D-CEO-08 | Remédiation | Sujet d'exercices personnalisé (5 exos/lacune) | 2026-05-08 |
| D-CEO-09 | Modes interface | Copie Unique + Batch | 2026-05-08 |
| D-CEO-10 | Format entrée | **PDF scanner 150 DPI, niveaux de gris** | **2026-06-05** |
| D-CEO-11 | Coût cible | **~$0.02/copie · ~$12/an** pour 540 copies | **2026-06-05** |
| D-CEO-12 | Diagnostic RAG | Ancré sur programme officiel MEN Burkina Faso (121 leçons 6e→3e) | **2026-06-08** |
| D-CEO-13 | Tests Hakili pré-chargés | TestRegistry : énoncé + barème auto · enseignant charge uniquement la copie | **2026-06-08** |
| D-CEO-14 | UI premium · marketing | Écran animé Hakili · 7 étapes en temps réel · logo pulsant · facturable parents | **2026-06-08** |
| D-CEO-15 | Génération PDF | Migration ReportLab → **XeLaTeX + Jinja2** (fallback ReportLab si xelatex absent) | **2026-06-11** |
| **D-CEO-16** | **Mode correction** | **Correction assistée : IA propose, enseignant valide dans l'interface** | **2026-06-11** |
| **D-CEO-17** | **Objectif central** | **Diagnostic approfondi = valeur principale — rapport centré sur les lacunes** | **2026-06-11** |
| **D-CEO-18** | **Portail de consultation** | **Persistance Neon Postgres + login par rôle — scaffolding, pipeline non câblé** | **2026-07-09** |
| **D-CEO-19** | **Câblage pipeline ↔ Neon** | **5 points d'injection DB, comptes seed idempotents, pool_pre_ping, comparaison chronologique (date_soumission), logs fichier** | **2026-07-15** |
| **D-CEO-20** | **Élèves/profs → Google Sheets** | **Table ELEVE supprimée, COPIE.identifiant_hakili ; élève choisi explicitement, bloqué avant appel IA si absent des Sheets** | **2026-07-17** |
| **D-CEO-21** | **Login → Sheet profs** | **Table UTILISATEUR (+ CENTRE) supprimée, table `credentials` (email + password_hash) ; le Sheet fait foi à chaque connexion** | **2026-07-17** |
| **D-CEO-22** | **Liste de centres autorisée** | **`CENTRES_AUTORISES` dans `centre_normalizer.py` ; alerte `[SHEETS WARNING]` sur centre non reconnu, ligne conservée ; même normalisation lecture ↔ permissions** | **2026-07-17** |
| **D-CEO-23** | **Vue Responsable — tendance** | **Pastille vert/orange/rouge/gris sur les 2 dernières notes, `SEUIL_TENDANCE` dans `tendance.py`, chargement groupé par centre, baisses triées en premier** | **2026-07-18** |
| **D-CEO-24** | **Vue Enseignant — profil élève** | **Sélection déroulante restreinte + profil détaillé (tendance réutilisée, copies chronologiques, documents) ; bug de permission `can_access_eleve`/enseignant corrigé** | **2026-07-18** |
| **D-CEO-25** | **Connexion nom+PIN, centres dérivés** | **Table `credentials` supprimée, rôle+PIN lus dans le Sheet personnel, regroupement par (nom, prénom) ; `CENTRES_AUTORISES` remplacée par `deriver_centres()` (détection de centre suspect, plus de liste figée)** | **2026-07-20** |
