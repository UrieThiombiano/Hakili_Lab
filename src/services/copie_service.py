import uuid
from datetime import date, datetime

from sqlalchemy.orm import Session

from src.db.models import Copie, Document


def create_copie(
    db: Session,
    copy_id: str,
    identifiant_hakili: str,
    classe: str,
    annee_scolaire: str,
    date_soumission: date | None = None,
) -> Copie:
    """Crée une nouvelle copie, rattachée à un élève via son identifiant
    Hakili (texte, calculé depuis les Google Sheets — voir
    src.integrations.google_sheets.build_identifiant_hakili)."""
    copie = Copie(
        copy_id=copy_id,
        identifiant_hakili=identifiant_hakili,
        classe=classe,
        annee_scolaire=annee_scolaire,
        date_soumission=date_soumission or datetime.now().date(),
    )
    db.add(copie)
    db.commit()
    db.refresh(copie)
    return copie


def get_copie_by_id(db: Session, copy_id: str) -> Copie | None:
    """Récupère une copie par son ID."""
    return db.query(Copie).filter_by(copy_id=copy_id).first()


def get_historique_eleve(db: Session, identifiant_hakili: str) -> list[Copie]:
    """Récupère l'historique complet d'un élève (toutes ses copies), triées
    de la plus récente à la plus ancienne."""
    return (
        db.query(Copie)
        .filter_by(identifiant_hakili=identifiant_hakili)
        .order_by(Copie.date_soumission.desc())
        .all()
    )


def get_copies_pour_identifiants(
    db: Session, identifiants_hakili: list[str]
) -> dict[str, list[Copie]]:
    """Charge en UNE seule requête (`WHERE identifiant_hakili IN (...)`) les
    copies de plusieurs élèves, regroupées ensuite en mémoire par
    identifiant_hakili. À utiliser dès qu'il faut calculer quelque chose
    (ex. tendance) pour toute une liste d'élèves — évite une requête par
    élève (N+1) pour un centre qui peut en compter plusieurs dizaines.

    Retourne un dict identifiant_hakili -> liste de copies (peut être vide
    pour un identifiant sans aucune copie — ne lève jamais d'erreur pour ça).
    """
    if not identifiants_hakili:
        return {}

    copies = (
        db.query(Copie)
        .filter(Copie.identifiant_hakili.in_(identifiants_hakili))
        .all()
    )

    par_identifiant: dict[str, list[Copie]] = {i: [] for i in identifiants_hakili}
    for copie in copies:
        par_identifiant.setdefault(copie.identifiant_hakili, []).append(copie)

    return par_identifiant


def add_document_to_copie(
    db: Session,
    copy_id: str,
    doc_type: str,  # "scan", "rapport", "remediation"
    fichier_bytes: bytes,
) -> Document:
    """Ajoute un document (scan/rapport/remédiation) à une copie."""
    document = Document(
        id=uuid.uuid4(),
        copy_id=copy_id,
        type=doc_type,
        fichier=fichier_bytes,
        date_creation=datetime.now().date(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def get_documents_for_copie(db: Session, copy_id: str) -> list[Document]:
    """Récupère tous les documents d'une copie."""
    return db.query(Document).filter_by(copy_id=copy_id).all()


def get_document_by_type(db: Session, copy_id: str, doc_type: str) -> Document | None:
    """Récupère un document spécifique (scan/rapport/remediation)."""
    return db.query(Document).filter_by(copy_id=copy_id, type=doc_type).first()


def update_copie_notes(db: Session, copy_id: str, notes_finales: float) -> Copie | None:
    """Met à jour les notes finales d'une copie."""
    copie = get_copie_by_id(db, copy_id)
    if copie:
        copie.notes_finales = notes_finales
        db.commit()
        db.refresh(copie)
    return copie


def update_copie_classe(db: Session, copy_id: str, classe: str) -> Copie | None:
    """Met à jour la classe d'une copie (ex: valeur posée avant transcription,
    remplacée par la classe réellement extraite de l'en-tête)."""
    copie = get_copie_by_id(db, copy_id)
    if copie:
        copie.classe = classe
        db.commit()
        db.refresh(copie)
    return copie
