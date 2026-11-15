"""Modèle de données : mesures, signalements, alertes, journal de décisions."""
from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def now():
    return datetime.now(timezone.utc)


class Mesure(Base):
    __tablename__ = "mesures"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quartier: Mapped[str] = mapped_column(String(40), index=True)
    type: Mapped[str] = mapped_column(String(20), index=True)      # air | bruit
    valeur: Mapped[float] = mapped_column(Float)
    unite: Mapped[str] = mapped_column(String(20))
    horodatage: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    statut_qualite: Mapped[str] = mapped_column(String(30), default="valide")  # valide | hors_plage | suspect
    statut: Mapped[str] = mapped_column(String(40), default="Mesure observée")
    alerte_id: Mapped[int | None] = mapped_column(ForeignKey("alertes.id"), nullable=True)


class Signalement(Base):
    __tablename__ = "signalements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String(20), unique=True)
    type: Mapped[str] = mapped_column(String(20))
    quartier: Mapped[str] = mapped_column(String(40))
    lieu: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    statut: Mapped[str] = mapped_column(String(40), default="Reçu")   # Reçu | Qualifié | Rejeté
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    alerte_id: Mapped[int | None] = mapped_column(ForeignKey("alertes.id"), nullable=True)


class Alerte(Base):
    __tablename__ = "alertes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String(20), unique=True)
    titre: Mapped[str] = mapped_column(String(160))
    quartier: Mapped[str] = mapped_column(String(40), index=True)
    type: Mapped[str] = mapped_column(String(20))
    priorite: Mapped[str] = mapped_column(String(20))               # Haute | Moyenne
    statut: Mapped[str] = mapped_column(String(30), default="Créée")
    action_proposee: Mapped[str] = mapped_column(String(60))
    hypothese: Mapped[str] = mapped_column(Text, default="")
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    journal: Mapped[list["Decision"]] = relationship(back_populates="alerte", order_by="Decision.id")


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alerte_id: Mapped[int] = mapped_column(ForeignKey("alertes.id"), index=True)
    action: Mapped[str] = mapped_column(String(120))
    motif: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20))
    auteur: Mapped[str] = mapped_column(String(40), default="système")
    horodatage: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    alerte: Mapped[Alerte] = relationship(back_populates="journal")