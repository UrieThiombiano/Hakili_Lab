# -*- coding: utf-8 -*-
"""
Génère docs/guide_expressions_maths_pdf.pdf avec la chaîne EXACTE du projet :
Jinja2 -> HTML+CSS -> xhtml2pdf, police Unicode via ReportLab, et les helpers
réels de src/pipeline/math_format.py pour les exemples live.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\Urie\OneDrive\Desktop\Hakili-Correction")
sys.path.insert(0, str(PROJECT_ROOT))

from jinja2 import Environment, BaseLoader
from markupsafe import Markup

from src.pipeline.math_format import math_to_html, humanize_ids_in_text
from src.pipeline.pdf_report_html import _register_unicode_font, _safe_text

FONT = _register_unicode_font()


def render(s: str) -> Markup:
    """Pipeline complet appliqué à un texte IA (identique à _cm du projet)."""
    return Markup(math_to_html(_safe_text(humanize_ids_in_text(s))))


# ── Exemples live : (entrée brute LLM, rendu calculé à la génération) ─────────
RAW_EXAMPLES = [
    "sqrt(49) = 7",
    "sqrt(a^2 + b^2)",
    "x^2 - 5x + 6 = 0",
    "2**10 = 1024",
    "(3/4) + (1/6) = 11/12",
    "7/12 des eleves ont reussi",
    "Test du 06/07/2026 : note 12,5/20",
    "a <= b => a + c <= b + c",
    "x != 0 et u_n = u_1 + (n-1) * r",
    "\\frac{22}{7} ~ 3.14",
    "\\sqrt{2} \\times \\pi",
    "Aire = pi * R2 = 3,14 * 25 cm2",
    "2⁻² = 1/4",
    "x ∈ ℝ et [AB] ⊥ [CD]",
    "A ∪ B et A ∩ B",
]
EXAMPLES = [(raw, render(raw)) for raw in RAW_EXAMPLES]

SNIPPET_PROMPT = """\
NOTATION MATHÉMATIQUE (obligatoire) :
- Écris les maths en ASCII simple, JAMAIS en LaTeX ni en Markdown.
- Racine : sqrt(x)   Puissance : x^2   Fraction : (a/b)
- Indice : u_1       Pi : pi           Comparaison : <=  >=  !=
"""

SNIPPET_PASS_A = """\
def ascii_math_upgrade(s: str) -> str:
    \"\"\"Notations informatiques -> symboles Unicode (AVANT échappement HTML,
    car <= et -> contiennent des caractères HTML).\"\"\"
    # 1. LaTeX résiduel -> formes ASCII gérées en aval (défense en profondeur)
    s = re.sub(r'\\\\[dt]?frac\\{([^{}]+)\\}\\{([^{}]+)\\}', r'(\\1/\\2)', s)
    s = re.sub(r'\\\\sqrt\\{([^{}]+)\\}', r'sqrt(\\1)', s)
    for cmd, sym in [(r'\\times','×'),(r'\\cdot','×'),(r'\\pi','π'),
                     (r'\\leq','≤'),(r'\\geq','≥'),(r'\\neq','≠')]:
        s = s.replace(cmd, sym)
    # 2. Comparaisons/flèches — L'ORDRE COMPTE : <=> avant <= et =>
    s = re.sub(r'\\s*<=>\\s*', ' équivaut à ', s)
    s = re.sub(r'\\s*<=\\s*',  ' ≤ ', s)
    s = re.sub(r'\\s*>=\\s*',  ' ≥ ', s)
    s = re.sub(r'\\s*(?:=>|->)\\s*',   ' → ', s)
    s = re.sub(r'\\s*(?:=/=|!=)\\s*',  ' ≠ ', s)
    # 3. Puissance Python 2**3 -> 2^3 (rendue en <sup> à la passe B)
    s = s.replace('**', '^')
    # 4. ~ d'approximation entre deux valeurs -> ≈
    s = re.sub(r'(?<=[\\s\\d])~(?=\\s?\\d)', '≈', s)
    # 5. Multiplication "*" entre deux termes -> ×
    s = re.sub(r'(?<=[A-Za-z0-9)])\\*(?=[A-Za-z0-9(])', '×', s)
    s = re.sub(r'(?<=[A-Za-z0-9)])\\s+\\*\\s+(?=[A-Za-z0-9(])', ' × ', s)
    return s
"""

SNIPPET_PASS_B = """\
_SUP  = re.compile(r'\\^(\\{[^{}]*\\}|\\([^()]*\\)|[+-]?[A-Za-z0-9]+|[+-])')
_SQRT = re.compile(r'sqrt\\(((?:[^()]*|\\([^()]*\\))*)\\)', re.IGNORECASE)
_FRAC = re.compile(r'\\((\\d+)/(\\d+)\\)')
# Fraction nue "7/12" : jamais adjacente à un chiffre, un slash, un point
# ou une virgule -> protège les dates (06/07/2026) et les décimaux.
_FRAC_BARE = re.compile(r'(?<![\\d/.,_])(\\d{1,3})/(\\d{1,4})(?![\\d/])')
# Indice : LETTRE ISOLÉE + underscore ("u_1" oui, "copy_id" non)
_SUB = re.compile(r'\\b([A-Za-z])_([A-Za-z0-9]{1,2})\\b')

def math_to_html(s: str) -> str:
    s = ascii_math_upgrade(s)                      # passe A
    s = s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
    def _sup(m):
        inner = m.group(1).strip('{}()')
        return f'<sup>{inner}</sup>'
    # sqrt(expr) -> √expr, ou √(expr) si expression composée
    def _sqrt(m):
        inner = _SUP.sub(_sup, m.group(1).strip())
        return f'√{inner}' if inner.isalnum() else f'√({inner})'
    s = _SQRT.sub(_sqrt, s)
    # Exposants AVANT fractions : dans "2^3/2^5", le 3/2 ne doit
    # pas devenir une fraction.
    s = _SUP.sub(_sup, s)
    frac = lambda m: (f'<sup>{m.group(1)}</sup>'
                      f'&frasl;<sub>{m.group(2)}</sub>')
    s = _FRAC.sub(frac, s)
    s = _FRAC_BARE.sub(frac, s)
    s = _SUB.sub(r'\\1<sub>\\2</sub>', s)            # u_1 -> u indice 1
    s = re.sub(r'\\bpi\\b', 'π', s)
    return s   # à marquer Markup(...) côté template Jinja2
"""

SNIPPET_SAFE = """\
# Symboles HORS répertoire WGL4 -> remplacement lisible par un élève.
# WGL4 = socle commun des polices courantes : ≤ ≥ ≠ ≈ ± × ÷ − √ ∞ ° π → ≡
# et le grec de base y figurent -> CONSERVÉS tels quels.
# Clés notées en échappements \\uXXXX : ces symboles ne passent justement
# pas dans toutes les polices (y compris celle de ce bloc de code !) et
# les échappements survivent à tout copier-coller.
_MATH_SAFE = {
    "\\u2115": "N", "\\u2124": "Z",   # ensembles N et Z (double barre)
    "\\u211a": "Q", "\\u211d": "R",   # ensembles Q et R (double barre)
    "\\u20d7": "",                    # flèche combinante de vecteur AB
    "\\u21d2": " → ",                 # double flèche d'implication
    "\\u21d4": " équivaut à ",        # double flèche d'équivalence
    "\\u2208": " appartient à ", "\\u2209": " n'appartient pas à ",
    "\\u2282": " inclus dans ", "\\u222a": " U ", "\\u2229": " inter ",
    "\\u22c5": " × ",                 # point de multiplication
    "\\u2220": "angle ", "\\u22a5": " perpendiculaire à ",
    "\\u2225": " // ",                # parallèles
}
# Exposants Unicode (2 puissance -2, etc.) traités par SÉQUENCE :
# "2\\u207b\\u00b2" -> "2^-2" -> UN SEUL <sup>-2</sup> au rendu.
_SUP_CHARS = "".join(map(chr, [0x2070, 0xB9, 0xB2, 0xB3,
                               *range(0x2074, 0x207A),      # 4 à 9
                               0x207F, 0x207A, 0x207B]))    # n + -
_SUPER_MAP = str.maketrans(_SUP_CHARS, "0123456789n+-")
_SUPER_RUN = re.compile(f"[{_SUP_CHARS}]+")

def _safe_text(s: str) -> str:
    s = _SUPER_RUN.sub(lambda m: "^" + m.group(0).translate(_SUPER_MAP), s)
    for char, repl in _MATH_SAFE.items():
        s = s.replace(char, repl)
    return re.sub(r" {2,}", " ", s)
"""

SNIPPET_FONT = """\
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from xhtml2pdf import pisa

# Une police TTF couvrant WGL4, essayée dans l'ordre :
CANDIDATES = [
    r"C:\\Windows\\Fonts\\arialuni.ttf",   # Arial Unicode MS (Office)
    r"C:\\Windows\\Fonts\\seguisym.ttf",   # Segoe UI Symbol (Win10+)
    r"C:\\Windows\\Fonts\\arial.ttf",      # Arial standard
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",   # Linux
]
for path in CANDIDATES:
    if Path(path).exists():
        pdfmetrics.registerFont(TTFont("HakFont", path))
        registerFontFamily("HakFont", normal="HakFont")
        break

html = jinja_env.get_template("rapport.html.j2").render(**contexte)
with open("rapport.pdf", "wb") as f:
    result = pisa.CreatePDF(html, dest=f, encoding="utf-8")
# puis dans le CSS du template :  body { font-family: "HakFont"; }
"""

TEMPLATE = """\
<html>
<head>
<style>
    @page {
        size: A4;
        margin: 2cm 1.8cm 2.2cm 1.8cm;
        @frame footer_frame {
            -pdf-frame-content: footer;
            bottom: 0.8cm; left: 1.8cm; width: 17.4cm; height: 0.8cm;
        }
    }
    body { font-family: "{{ font }}"; font-size: 9.5pt; color: #1c2833; }
    h1 { font-size: 17pt; color: #1a5276; margin-bottom: 2pt; }
    .subtitle { font-size: 10.5pt; color: #566573; margin-top: 0; }
    h2 { font-size: 12.5pt; color: #1a5276; border-bottom: 1px solid #aed6f1;
         padding-bottom: 2pt; margin-top: 16pt; }
    h3 { font-size: 10.5pt; color: #21618c; margin-top: 10pt; }
    p { line-height: 1.45; margin: 5pt 0; }
    table { width: 100%; border-collapse: collapse; margin: 6pt 0; }
    th { background-color: #1a5276; color: white; font-size: 8.5pt;
         padding: 4pt 6pt; text-align: left; }
    td { border: 0.5pt solid #b8c4ce; padding: 3.5pt 6pt; font-size: 9pt;
         vertical-align: top; }
    tr.alt td { background-color: #eef4f9; }
    pre { background-color: #f2f4f4; border: 0.5pt solid #ccd1d1;
          padding: 6pt 8pt; font-family: Courier; font-size: 7.6pt;
          line-height: 1.35; margin: 6pt 0; }
    .mono { font-family: Courier; font-size: 8.5pt; }
    .note { background-color: #fef9e7; border: 0.5pt solid #f4d03f;
            padding: 5pt 8pt; font-size: 9pt; margin: 6pt 0; }
    .keybox { background-color: #eaf2f8; border: 0.5pt solid #85c1e9;
              padding: 6pt 8pt; margin: 6pt 0; }
    ul, ol { margin: 4pt 0 4pt 14pt; }
    li { margin: 2.5pt 0; line-height: 1.4; }
    #footer { font-size: 8pt; color: #808b96; text-align: center; }
</style>
</head>
<body>

<div id="footer">Guide technique — expressions mathématiques dans un PDF généré par IA — {{ date }} — page <pdf:pagenumber> / <pdf:pagecount></div>

<h1>Expressions mathématiques lisibles dans un PDF</h1>
<p class="subtitle">Guide reproductible — chaîne de rendu du projet Hakili Lab (correction assistée par IA)<br/>
{{ date }} — <b>ce document a été généré avec la chaîne décrite ci-dessous</b> : les exemples de la section 6 sont calculés par le vrai code au moment de la génération.</p>

<h2>1. Le problème</h2>
<p>Les textes produits par les LLM (corrections, diagnostics, exercices) écrivent les mathématiques
en <b>notation informatique</b> : <span class="mono">sqrt(25)</span>, <span class="mono">x**2</span>,
<span class="mono">&lt;=</span>, <span class="mono">(3/4)</span>, voire du LaTeX brut
(<span class="mono">\\frac{7}{12}</span>) — même quand le prompt l'interdit. Rendu tel quel dans un PDF,
c'est illisible pour un élève ou un enseignant. Et la solution « évidente » (LaTeX/MathJax) est lourde :
elle impose une distribution TeX ou un navigateur headless.</p>
<p><b>Notre approche :</b> rester en pur Python, convertir la notation informatique en
<b>symboles Unicode + balises HTML <span class="mono">&lt;sup&gt;/&lt;sub&gt;</span></b> par regex,
et générer le PDF depuis du HTML. Niveau collège (6e–3e), cela couvre tout le besoin :
racines, puissances, fractions, indices, comparaisons, ensembles, géométrie.</p>

<h2>2. La chaîne de rendu et les outils</h2>
<table>
    <tr><th width="22%">Outil</th><th width="20%">Version</th><th>Rôle</th></tr>
    <tr><td><b>Jinja2</b></td><td>&ge; 3.x</td><td>Template HTML du rapport (autoescape actif ; les fragments maths convertis sont marqués <span class="mono">Markup</span>)</td></tr>
    <tr class="alt"><td><b>xhtml2pdf</b></td><td>&ge; 0.2.14</td><td>Conversion HTML+CSS → PDF (<span class="mono">pisa.CreatePDF</span>), pur Python</td></tr>
    <tr><td><b>ReportLab</b></td><td>(dépendance de xhtml2pdf)</td><td>Moteur PDF sous-jacent + enregistrement des polices TTF Unicode</td></tr>
    <tr class="alt"><td><b>MarkupSafe</b></td><td>&ge; 2.x</td><td>Marquage des fragments HTML sûrs (<span class="mono">Markup</span>)</td></tr>
    <tr><td><b>re</b> (stdlib)</td><td>—</td><td>Toute la conversion mathématique : un module de helpers purs, sans dépendance</td></tr>
</table>
<p>Flux : <b>texte LLM → normalisation regex → template Jinja2 → HTML+CSS → xhtml2pdf → PDF</b>.
Aucun LaTeX, aucun navigateur, aucune dépendance système : <span class="mono">pip install xhtml2pdf jinja2</span> suffit.</p>

<div class="keybox"><b>Décision de fond :</b> on ne cherche PAS à rendre du LaTeX. On se limite au
répertoire de symboles <b>WGL4</b> (socle garanti par les polices Windows/Linux courantes : ≤ ≥ ≠ ≈ ± × ÷ − √ ∞ ° π → ≡, grec de base)
plus <span class="mono">&lt;sup&gt;/&lt;sub&gt;</span> pour exposants, indices et fractions.
Tout symbole hors de ce socle est remplacé par du français lisible (section 5). Résultat : zéro carré « tofu » dans le PDF, quel que soit le poste.</div>

<h2>3. Étape 1 — Contraindre le LLM en amont (prompt)</h2>
<p>Première ligne de défense : imposer une notation ASCII <b>simple et régulière</b> dans le prompt système
de chaque tâche (correction, diagnostic, remédiation). Une notation régulière se convertit ensuite par regex de façon fiable :</p>
<pre>{{ snippet_prompt }}</pre>
<p>Les LLM fuient malgré tout (LaTeX résiduel, <span class="mono">**</span> Python, gras Markdown) :
c'est pour cela que la conversion aval rattrape AUSSI ces formes — <b>défense en profondeur</b>.
Ne comptez jamais sur le prompt seul.</p>

<h2>4. Étape 2 — Conversion regex en deux passes</h2>
<p>Un seul module de ~140 lignes, sans dépendance (regex stdlib uniquement), partagé entre le rendu PDF
et l'interface web. Deux fonctions publiques : <span class="mono">ascii_math_upgrade()</span> et
<span class="mono">math_to_html()</span>.</p>

<h3>Passe A — notations informatiques → symboles Unicode (AVANT échappement HTML)</h3>
<p>Cette passe traite <span class="mono">&lt;=</span>, <span class="mono">-&gt;</span>… qui contiennent
des caractères HTML : elle doit donc s'exécuter <b>avant</b> l'échappement de
<span class="mono">&amp; &lt; &gt;</span>.</p>
<pre>{{ snippet_pass_a }}</pre>

<h3>Passe B — structures (racines, exposants, fractions, indices) → HTML</h3>
<p>Après échappement HTML, on insère les balises <span class="mono">&lt;sup&gt;/&lt;sub&gt;</span>.
L'échappement systématique AVANT insertion des balises est ce qui permet de marquer le résultat
<span class="mono">Markup</span> sans risque : aucun HTML brut du LLM ne peut passer.</p>
<pre>{{ snippet_pass_b }}</pre>

<div class="note"><b>L'ordre des règles est la partie délicate — trois pièges vécus :</b>
<ul>
<li><span class="mono">&lt;=&gt;</span> doit être traité avant <span class="mono">&lt;=</span> et <span class="mono">=&gt;</span>, sinon « a &lt;=&gt; b » devient « a ≤ &gt; b ».</li>
<li>Les exposants avant les fractions : dans <span class="mono">2^3/2^5</span>, le « 3/2 » ne doit pas devenir une fraction.</li>
<li>Les fractions nues (<span class="mono">7/12</span>) exigent des gardes : jamais adjacentes à un chiffre, un slash, un point ou une virgule — sinon les dates (06/07/2026), les couples d'années et les décimaux sont détruits. De même l'indice <span class="mono">x_A</span> exige une lettre isolée, sinon <span class="mono">copy_id</span> devient « copy<sub>id</sub> ».</li>
</ul></div>

<h2>5. Étape 3 — Garde-fou police : le filtre WGL4</h2>
<p>Le LLM peut aussi émettre directement des symboles Unicode exotiques que les polices PDF ne
couvrent pas : l'appartenance ∈, la double flèche ⇔, les ensembles de nombres « double barre »
(U+211D pour R, U+2115 pour N), les flèches combinantes de vecteurs… Ils s'affichent alors en carrés
« tofu ». Avant tout rendu, un remplacement mappe chaque symbole <b>hors WGL4</b> vers du français
lisible par un élève — jamais vers du jargon ASCII :</p>
<div class="note"><b>Point important vérifié empiriquement :</b> ce filtre reste obligatoire
<b>même avec une police complète</b>. Segoe UI Symbol contient bien le glyphe U+211D (R double barre)
— ReportLab seul le dessine correctement — mais la chaîne xhtml2pdf le remplace quand même par un
carré. Ne vous fiez donc pas aux tables de couverture de la police : testez le rendu final, et
filtrez tout ce qui est hors WGL4.</div>
<pre>{{ snippet_safe }}</pre>

<h2>6. Démonstration — calculée par le vrai code à la génération de ce PDF</h2>
<p>Chaque ligne ci-dessous est passée dans le pipeline réel
(<span class="mono">_safe_text</span> puis <span class="mono">math_to_html</span>)
au moment où ce document a été généré :</p>
<table>
    <tr><th width="48%">Entrée brute (telle qu'écrite par le LLM)</th><th>Rendu dans le PDF</th></tr>
    {% for raw, rendered in examples %}
    <tr{% if loop.index is even %} class="alt"{% endif %}><td class="mono">{{ raw }}</td><td>{{ rendered }}</td></tr>
    {% endfor %}
</table>
<p style="font-size:8.5pt; color:#566573;">Note : les carrés encore visibles dans la colonne de
gauche (l'exposant Unicode « moins » U+207B, le R « double barre » U+211D) sont des symboles que la
police de cette colonne ne sait pas rendre — c'est précisément le tofu que le pipeline élimine,
comme le montre à chaque fois la colonne de droite.</p>

<h2>7. Étape 4 — Police Unicode et génération du PDF</h2>
<p>Dernière brique : xhtml2pdf n'embarque que les polices PDF de base (Helvetica…), qui ne couvrent pas
√ π ≤ ≥. Il faut enregistrer une police TTF du système via ReportLab, avec une liste de candidates
ordonnée et un repli, puis la référencer dans le CSS du template :</p>
<pre>{{ snippet_font }}</pre>
<div class="note"><b>Limites CSS de xhtml2pdf à connaître :</b> pas de flexbox ni de grid — mise en page
par tableaux ; sous-ensemble CSS 2.1 ; en-têtes/pieds de page via
<span class="mono">@frame</span> et <span class="mono">-pdf-frame-content</span> (utilisés dans ce document même).
Pour du contenu scolaire structuré (tableaux de notes, listes, paragraphes), c'est largement suffisant.</div>

<h2>8. Checklist d'intégration</h2>
<ol>
<li><span class="mono">pip install "xhtml2pdf&gt;=0.2.14" jinja2 markupsafe</span></li>
<li>Ajouter la consigne de notation ASCII (section 3) au prompt système de chaque tâche LLM.</li>
<li>Créer un module <span class="mono">math_format.py</span> autonome (regex stdlib uniquement) avec les deux passes de la section 4 — le garder pur le rend partageable entre le PDF et l'UI web, et testable unitairement.</li>
<li>Ajouter le filtre WGL4 (section 5) côté rendu PDF.</li>
<li>Enregistrer une police TTF Unicode via ReportLab et la déclarer dans le CSS (section 7).</li>
<li>Dans le template Jinja2 (autoescape actif), n'injecter les textes maths que via le pipeline complet, marqué <span class="mono">Markup</span> : <span class="mono">Markup(math_to_html(_safe_text(texte)))</span>.</li>
<li>Tester avec des cas pièges : dates (06/07/2026), notes (12,5/20), identifiants à underscore, <span class="mono">2^3/2^5</span>, LaTeX résiduel.</li>
</ol>

<p style="margin-top:14pt; color:#566573; font-size:8.5pt;">Ordre de grandeur : le module de conversion fait ~140 lignes,
le rendu PDF ~400 lignes template compris. Aucun service externe, fonctionne hors-ligne.</p>

</body>
</html>
"""


def main() -> None:
    env = Environment(loader=BaseLoader(), autoescape=True)
    from datetime import date
    months = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
              "août", "septembre", "octobre", "novembre", "décembre"]
    d = date.today()
    html = env.from_string(TEMPLATE).render(
        font=FONT,
        date=f"{d.day} {months[d.month]} {d.year}",
        examples=EXAMPLES,
        snippet_prompt=SNIPPET_PROMPT,
        snippet_pass_a=SNIPPET_PASS_A,
        snippet_pass_b=SNIPPET_PASS_B,
        snippet_safe=SNIPPET_SAFE,
        snippet_font=SNIPPET_FONT,
    )
    from xhtml2pdf import pisa
    out = PROJECT_ROOT / "docs" / "guide_expressions_maths_pdf.pdf"
    with open(out, "wb") as f:
        result = pisa.CreatePDF(html, dest=f, encoding="utf-8")
    print(f"erreurs={result.err} -> {out}")


if __name__ == "__main__":
    main()
