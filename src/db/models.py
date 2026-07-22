import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, Date, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import BYTEA, UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class UserRole(str, PyEnum):
    """Valeurs alignées sur la colonne `role` du Sheet profs (Google Sheets,
    source de vérité de l'identité — voir src/integrations/google_sheets.py)
    : ce n'est plus un type de colonne SQL depuis que l'identité des profs a
    quitté PostgreSQL, seulement un enum Python pour comparer proprement le
    profil choisi au login au rôle lu dans le Sheet."""
    admin = "administrateur"
    responsable_centre = "responsable"
    enseignant = "enseignant"


class Copie(Base):
    """L'identité de l'élève (nom, prénom, classe administrative, centre,
    contact) vit désormais dans les Google Sheets (src/integrations/
    google_sheets.py) — PostgreSQL ne stocke plus que ce qui concerne la
    correction elle-même : l'identifiant_hakili (texte, calculé depuis les
    Sheets) relie la copie à un élève sans dupliquer son identité en base."""
    __tablename__ = "copie"

    copy_id = Column(String(255), primary_key=True, nullable=False)
    identifiant_hakili = Column(String(255), nullable=False)
    classe = Column(String(50), nullable=False)
    annee_scolaire = Column(String(50), nullable=False)
    date_soumission = Column(Date, default=datetime.now, nullable=False)
    notes_finales = Column(Float, nullable=True)

    documents = relationship("Document", back_populates="copie")


class Document(Base):
    __tablename__ = "document"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    copy_id = Column(String(255), ForeignKey("copie.copy_id"), nullable=False)
    type = Column(String(50), nullable=False)  # "scan", "rapport", "remediation"
    fichier = Column(BYTEA, nullable=False)
    date_creation = Column(Date, default=datetime.now, nullable=False)

    copie = relationship("Copie", back_populates="documents")
