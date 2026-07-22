"""Contrôle d'accès aux élèves selon le profil de l'utilisateur connecté.

L'identité de l'utilisateur (rôle, affectations) vient du Sheet profs — voir
src.services.auth_service.authentifier(). `user` ici est donc un dict Sheet
enrichi du champ `role_enum` (UserRole, ajouté au login pour comparer
proprement), pas un objet base de données : il n'y a plus de table
UTILISATEUR portant cette identité.

Un enseignant ou un responsable peut avoir PLUSIEURS affectations (centre,
classe) — une ligne par affectation dans le Sheet enseignants (voir
src/integrations/google_sheets.py, _load_enseignants). `user["affectations"]`
est donc une LISTE de tuples (centre, classe) — classe=None pour un
responsable, qui n'est jamais filtré par classe. Un élève est accessible dès
qu'AU MOINS UNE affectation correspond."""
from sqlalchemy.orm import Session

from src.core.centre_normalizer import centres_correspondent
from src.core.classe_normalizer import meme_niveau
from src.db.models import UserRole


def _une_affectation_correspond(eleve: dict, affectations: list, *, avec_classe: bool) -> bool:
    """Vrai si AU MOINS UNE affectation (centre, classe) de l'utilisateur
    correspond à l'élève. `avec_classe` : True pour un enseignant (le niveau
    doit aussi correspondre, série ignorée — voir classe_normalizer.
    meme_niveau), False pour un responsable (centre seul, jamais de filtre
    classe)."""
    for centre, classe in affectations:
        if not centres_correspondent(eleve.get("centre"), centre):
            continue
        if avec_classe and not meme_niveau(eleve.get("classe"), classe):
            continue
        return True
    return False


def get_accessible_eleves(user: dict) -> list[dict]:
    """Retourne les élèves accessibles pour un utilisateur selon son rôle.
    Élèves ET utilisateur viennent tous les deux des Google Sheets — aucun
    accès base ici.

    Même critère que can_access_eleve ci-dessous — les deux DOIVENT rester
    cohérents (une divergence de ce type a déjà causé un bug par le passé),
    d'où le partage de _une_affectation_correspond."""
    from src.integrations.google_sheets import get_eleves

    eleves = get_eleves()

    if user["role_enum"] == UserRole.admin:
        return eleves

    affectations = user.get("affectations", [])

    if user["role_enum"] == UserRole.responsable_centre:
        return [e for e in eleves if _une_affectation_correspond(e, affectations, avec_classe=False)]
    if user["role_enum"] == UserRole.enseignant:
        return [e for e in eleves if _une_affectation_correspond(e, affectations, avec_classe=True)]

    return []


def can_access_eleve(db: Session, user: dict, eleve: dict) -> bool:
    """Vérifie si un utilisateur a le droit de consulter un élève donné
    (dict issu des Google Sheets — voir get_eleve_by_identifiant). Même
    critère que get_accessible_eleves ci-dessus."""
    if user["role_enum"] == UserRole.admin:
        return True

    affectations = user.get("affectations", [])

    if user["role_enum"] == UserRole.responsable_centre:
        return _une_affectation_correspond(eleve, affectations, avec_classe=False)
    if user["role_enum"] == UserRole.enseignant:
        return _une_affectation_correspond(eleve, affectations, avec_classe=True)

    return False
