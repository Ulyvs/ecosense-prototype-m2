"""Extensions du prototype : suivi citoyen d'un signalement et carte des alertes.

Les coordonnées des quartiers sont des points de repère issus de sources GPS publiques.
"""
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Signalement, Alerte

ROOT = Path(__file__).resolve().parent.parent
router = APIRouter()

# code quartier : (latitude, longitude, nom affiché)
# Sources : GPS publics (gps-latitude-longitude.com, Global Detention Project pour le commissariat
# de Béni Makada, Bamwor pour Résidence Malabata). Points de repère, pas des limites administratives.
COORDONNEES = {
    "Q-CV": (35.7760, -5.8070, "Centre-ville"),   # axe Boulevard Pasteur / Place de France
    "Q-MB": (35.7840, -5.7596, "Malabata"),       # Résidence Malabata
    "Q-BM": (35.7500, -5.8165, "Béni Makada"),    # avenue Abi Dardae
}
ETAPES = ["Reçu", "Qualifié", "Alerte créée"]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/api/suivi/{reference}")
def suivi(reference: str, db: Session = Depends(get_db)):
    """Suivi public d'un signalement, par sa référence. Pas de description ni de données personnelles."""
    s = db.scalar(select(Signalement).where(Signalement.reference == reference.strip().upper()))
    if not s:
        raise HTTPException(404, "Aucun signalement avec cette référence")
    alerte = db.get(Alerte, s.alerte_id) if s.alerte_id else None
    niveau = 0
    if s.statut == "Qualifié":
        niveau = 1
    if alerte:
        niveau = 2
    return {
        "reference": s.reference,
        "type": s.type,
        "quartier": COORDONNEES.get(s.quartier, (0, 0, s.quartier))[2],
        "lieu": s.lieu,
        "statut": s.statut,
        "date": s.cree_le.isoformat(),
        "etapes": [{"nom": nom, "atteinte": i <= niveau} for i, nom in enumerate(ETAPES)],
        "alerte": alerte.reference if alerte else None,
        "alerte_statut": alerte.statut if alerte else None,
    }


@router.get("/api/carte")
def carte(db: Session = Depends(get_db)):
    """Alertes avec position. Plusieurs alertes dans un même quartier sont décalées légèrement."""
    alertes = db.scalars(select(Alerte).order_by(Alerte.id)).all()
    compteur = {}
    points = []
    for a in alertes:
        lat, lon, nom = COORDONNEES.get(a.quartier, (None, None, a.quartier))
        k = compteur.get(a.quartier, 0)
        compteur[a.quartier] = k + 1
        points.append({
            "reference": a.reference,
            "titre": a.titre,
            "statut": a.statut,
            "priorite": a.priorite,
            "quartier": nom,
            "lat": lat + 0.0009 * k if lat is not None else None,
            "lon": lon + 0.0009 * k if lon is not None else None,
        })
    return points


@router.get("/suivi", include_in_schema=False)
def page_suivi():
    return FileResponse(ROOT / "static" / "suivi.html")


@router.get("/carte", include_in_schema=False)
def page_carte():
    return FileResponse(ROOT / "static" / "carte.html")
