"""API EcoSense (prototype). Données fictives.

Accès :
- public : signaler, suivre un signalement, consulter la carte et les alertes ;
- agent : qualifier un signalement en alerte ;
- décideur : prendre les décisions sur les alertes, réinitialiser la démonstration.
Le rôle vient d'un jeton obtenu par POST /api/connexion (en-tête Authorization: Bearer ...).
Les capteurs envoient leurs relevés avec l'en-tête X-Capteur-Cle.
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from .db import engine, SessionLocal, Base
from .models import Mesure, Signalement, Alerte, Decision
from .rules import qualite, evaluer
from .workflow import transition_possible, actions_permises
from .auth import identite, verifier_mot_de_passe, emettre_jeton, exiger_capteur, COMPTES
from .extensions import router as extensions_router

QUARTIERS = {"Q-CV": "Centre-ville", "Q-MB": "Malabata", "Q-BM": "Béni Makada"}
ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def cycle_de_vie(_app):
    Base.metadata.create_all(bind=engine)
    from .seed import amorcer_si_vide
    amorcer_si_vide()
    yield


app = FastAPI(title="EcoSense – prototype", version="0.3.0", lifespan=cycle_de_vie)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.include_router(extensions_router)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- Schémas ----------
class LoginIn(BaseModel):
    compte: str
    mot_de_passe: str


class MesureIn(BaseModel):
    quartier: str
    type: str = Field(pattern="^(air|bruit)$")
    valeur: float
    unite: str
    horodatage: datetime


class SignalementIn(BaseModel):
    type: str = Field(pattern="^(visuel|bruit|air)$")
    quartier: str
    lieu: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=20, max_length=500)


class DecisionIn(BaseModel):
    action: str
    motif: str = Field(min_length=10, max_length=500)


# ---------- Connexion ----------
@app.post("/api/connexion")
def connexion(c: LoginIn):
    if not verifier_mot_de_passe(c.compte, c.mot_de_passe):
        raise HTTPException(401, "Identifiant ou mot de passe incorrect")
    return {"jeton": emettre_jeton(c.compte), "compte": c.compte,
            "role": COMPTES[c.compte]["role"], "nom": COMPTES[c.compte]["nom"]}


@app.get("/api/moi")
def moi(authorization: str | None = Header(default=None)):
    compte, role = identite(authorization)
    return {"compte": compte, "role": role}


# ---------- Mesures ----------
def _valeurs_valides(db: Session, quartier: str, type_mesure: str) -> list[float]:
    rows = db.scalars(
        select(Mesure).where(Mesure.quartier == quartier, Mesure.type == type_mesure,
                             Mesure.statut_qualite == "valide").order_by(Mesure.horodatage)
    ).all()
    return [r.valeur for r in rows]


@app.post("/api/mesures", status_code=201)
def ingerer(m: MesureIn, x_capteur_cle: str | None = Header(default=None), db: Session = Depends(get_db)):
    exiger_capteur(x_capteur_cle)
    if m.quartier not in QUARTIERS:
        raise HTTPException(422, "Quartier inconnu")
    horo = m.horodatage if m.horodatage.tzinfo else m.horodatage.replace(tzinfo=timezone.utc)
    doublon = db.scalar(select(Mesure.id).where(Mesure.quartier == m.quartier, Mesure.type == m.type,
                                                Mesure.horodatage == horo))
    if doublon:
        raise HTTPException(409, "Mesure déjà enregistrée pour ce quartier et cet horodatage")
    statut_q = qualite(m.type, m.valeur)
    mesure = Mesure(quartier=m.quartier, type=m.type, valeur=m.valeur, unite=m.unite,
                    horodatage=horo, statut_qualite=statut_q)
    db.add(mesure)
    db.flush()
    declenche = None
    if statut_q == "valide":
        valeurs = _valeurs_valides(db, m.quartier, m.type)
        ouverte = db.scalar(select(Alerte.id).where(Alerte.quartier == m.quartier, Alerte.type == m.type,
                                                    Alerte.statut != "Clôturée"))
        decl = evaluer(m.type, QUARTIERS[m.quartier], valeurs)
        if decl and not ouverte:
            alerte = Alerte(reference=f"AL-{datetime.now().year}-{db.scalar(func.count(Alerte.id)) + 1:03d}",
                            titre=decl.titre, quartier=m.quartier, type=m.type, priorite=decl.priorite,
                            statut="Créée", action_proposee=decl.action, hypothese=decl.hypothese)
            db.add(alerte)
            db.flush()
            mesure.alerte_id = alerte.id
            declenche = alerte.reference
    db.commit()
    return {"id": mesure.id, "statut_qualite": statut_q, "alerte_creee": declenche}


@app.get("/api/mesures")
def lister_mesures(quartier: str | None = None, type: str | None = None, db: Session = Depends(get_db)):
    q = select(Mesure).order_by(Mesure.horodatage.desc()).limit(200)
    if quartier:
        q = q.where(Mesure.quartier == quartier)
    if type:
        q = q.where(Mesure.type == type)
    return [{"id": r.id, "quartier": r.quartier, "type": r.type, "valeur": r.valeur, "unite": r.unite,
             "horodatage": r.horodatage.isoformat(), "statut_qualite": r.statut_qualite, "statut": r.statut}
            for r in db.scalars(q)]


# ---------- Signalements ----------
@app.post("/api/signalements", status_code=201)
def signaler(s: SignalementIn, db: Session = Depends(get_db)):
    if s.quartier not in QUARTIERS:
        raise HTTPException(422, "Quartier inconnu")
    n = db.scalar(func.count(Signalement.id)) + 42
    ref = f"SIG-{datetime.now().year}-{n:04d}"
    obj = Signalement(reference=ref, **s.model_dump())
    db.add(obj)
    db.commit()
    return {"reference": ref, "statut": obj.statut,
            "message": "Reçu. Le signalement devient une alerte seulement après qualification par un agent."}


@app.get("/api/signalements")
def lister_signalements(db: Session = Depends(get_db)):
    return [{"reference": r.reference, "type": r.type, "quartier": r.quartier, "lieu": r.lieu,
             "statut": r.statut} for r in db.scalars(select(Signalement).order_by(Signalement.id.desc()))]


@app.post("/api/signalements/{ref}/qualifier")
def qualifier(ref: str, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    _, role = identite(authorization)
    if role != "agent":
        raise HTTPException(403, "Seul un agent peut qualifier un signalement")
    s = db.scalar(select(Signalement).where(Signalement.reference == ref))
    if not s:
        raise HTTPException(404, "Signalement introuvable")
    if s.statut != "Reçu":
        raise HTTPException(409, "Signalement déjà traité")
    alerte = Alerte(reference=f"AL-{datetime.now().year}-{db.scalar(func.count(Alerte.id)) + 1:03d}",
                    titre=f"Signalement {s.reference} — {QUARTIERS[s.quartier]}", quartier=s.quartier,
                    type=s.type, priorite="Moyenne", statut="Créée",
                    action_proposee="Inspecter la zone",
                    hypothese="Dépôt signalé par un citoyen, à confirmer sur place.")
    db.add(alerte)
    db.flush()
    s.statut = "Qualifié"
    s.alerte_id = alerte.id
    db.commit()
    return {"reference": s.reference, "alerte": alerte.reference}


# ---------- Alertes ----------
def _alerte_dict(a: Alerte, role: str) -> dict:
    return {
        "id": a.id, "reference": a.reference, "titre": a.titre, "quartier": a.quartier,
        "quartier_nom": QUARTIERS.get(a.quartier, a.quartier), "type": a.type, "priorite": a.priorite,
        "statut": a.statut, "action_proposee": a.action_proposee, "hypothese": a.hypothese,
        "cree_le": a.cree_le.isoformat() if a.cree_le else None,
        "actions_permises": actions_permises(a.statut, role),
        "journal": [{"action": d.action, "motif": d.motif, "role": d.role, "auteur": d.auteur,
                     "horodatage": d.horodatage.isoformat()} for d in a.journal],
    }


@app.get("/api/alertes")
def lister_alertes(statut: str | None = None, quartier: str | None = None,
                   authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    _, role = identite(authorization)
    q = select(Alerte).order_by(Alerte.cree_le.desc(), Alerte.id.desc())
    if statut:
        q = q.where(Alerte.statut == statut)
    if quartier:
        q = q.where(Alerte.quartier == quartier)
    return [_alerte_dict(a, role) for a in db.scalars(q)]


@app.get("/api/alertes/{alerte_id}")
def detail_alerte(alerte_id: int, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    _, role = identite(authorization)
    a = db.get(Alerte, alerte_id)
    if not a:
        raise HTTPException(404, "Alerte introuvable")
    mesures = db.scalars(
        select(Mesure).where(Mesure.quartier == a.quartier, Mesure.type == a.type)
        .order_by(Mesure.horodatage.desc()).limit(10)
    ).all()
    d = _alerte_dict(a, role)
    d["releves"] = [{"valeur": m.valeur, "unite": m.unite, "horodatage": m.horodatage.isoformat()} for m in mesures]
    return d


@app.post("/api/alertes/{alerte_id}/decisions")
def decider(alerte_id: int, d: DecisionIn, authorization: str | None = Header(default=None),
            db: Session = Depends(get_db)):
    compte, role = identite(authorization)
    a = db.get(Alerte, alerte_id)
    if not a:
        raise HTTPException(404, "Alerte introuvable")
    suivant = transition_possible(a.statut, role)
    if not suivant:
        raise HTTPException(403, f"Action non autorisée pour le rôle « {role} » au statut « {a.statut} »")
    avant = a.statut
    a.statut = suivant
    db.add(Decision(alerte_id=a.id, action=f"{avant} → {suivant}", motif=d.motif, role=role, auteur=compte))
    db.commit()
    return _alerte_dict(a, role)


# ---------- Démonstration ----------
@app.post("/api/demo/reinitialiser", status_code=201)
def reinitialiser(authorization: str | None = Header(default=None)):
    _, role = identite(authorization)
    if role != "decideur":
        raise HTTPException(403, "Réservé au décideur")
    from .seed import reinitialiser_base
    reinitialiser_base()
    return {"message": "Base réinitialisée avec les scénarios de démonstration"}


@app.get("/", include_in_schema=False)
def accueil():
    return FileResponse(ROOT / "static" / "index.html")