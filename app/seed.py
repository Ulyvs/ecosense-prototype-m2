"""Données fictives : trois scénarios cohérents (Centre-ville, Malabata, Béni Makada)."""
from datetime import datetime, timezone
from sqlalchemy import select, func
from .db import SessionLocal, Base, engine
from .models import Mesure, Alerte, Signalement, Decision
from .rules import qualite, evaluer

BASE = datetime(2026, 11, 12, 8, 0, tzinfo=timezone.utc)


def _ingerer(db, quartier_nom, quartier, type_, valeurs, unite, debut_h=0, pas_h=2):
    from datetime import timedelta
    for i, v in enumerate(valeurs):
        h = BASE + timedelta(hours=debut_h + i * pas_h)
        db.add(Mesure(quartier=quartier, type=type_, valeur=v, unite=unite, horodatage=h,
                      statut_qualite=qualite(type_, v)))
    db.flush()


def reinitialiser_base():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 1. Centre-ville : hausse des PM2.5 → alerte à valider
        _ingerer(db, "Centre-ville", "Q-CV", "air", [38, 44, 52, 61, 68, 74], "µg/m³ PM2.5")
        a1 = Alerte(reference="AL-2026-001", titre="Hausse des PM2.5 — Centre-ville", quartier="Q-CV",
                    type="air", priorite="Haute", statut="À valider", action_proposee="Vérifier le capteur",
                    hypothese="Hausse réelle de la pollution, ou dérive du capteur : à vérifier sur le terrain.",
                    cree_le=BASE)
        db.add(a1); db.flush()
        db.scalars(select(Mesure).where(Mesure.quartier == "Q-CV")).all()
        for m in db.scalars(select(Mesure).where(Mesure.quartier == "Q-CV")):
            m.alerte_id = a1.id
        db.add(Decision(alerte_id=a1.id, action="Créée → En qualification", motif="Relevés croissants sur la journée.", role="agent"))
        db.add(Decision(alerte_id=a1.id, action="En qualification → À valider", motif="Hypothèse de dérive capteur à trancher.", role="agent"))
        # 2. Malabata : bruit → en qualification (prévision indisponible)
        _ingerer(db, "Malabata", "Q-MB", "bruit", [68, 74], "dB(A) LAeq", debut_h=13, pas_h=24)
        a2 = Alerte(reference="AL-2026-002", titre="Bruit élevé — Malabata", quartier="Q-MB", type="bruit",
                    priorite="Moyenne", statut="En qualification", action_proposee="Renforcer la surveillance",
                    hypothese="Nuisance sonore répétée, cause non établie (trafic, chantier, activité).",
                    cree_le=BASE)
        db.add(a2); db.flush()
        for m in db.scalars(select(Mesure).where(Mesure.quartier == "Q-MB")):
            m.alerte_id = a2.id
        db.add(Decision(alerte_id=a2.id, action="Créée → En qualification", motif="Deux soirées au-dessus du seuil.", role="agent"))
        # 3. Béni Makada : signalement qualifié → inspection proposée
        s = Signalement(reference="SIG-2026-0041", type="visuel", quartier="Q-BM", lieu="Rue près du marché",
                        description="Dépôt de déchets sur le trottoir depuis plusieurs jours.", statut="Qualifié",
                        cree_le=BASE)
        db.add(s)
        a3 = Alerte(reference="AL-2026-003", titre="Dépôt de déchets signalé — Béni Makada", quartier="Q-BM",
                    type="visuel", priorite="Moyenne", statut="Créée", action_proposee="Inspecter la zone",
                    hypothese="Dépôt signalé par un citoyen, à confirmer sur place.", cree_le=BASE)
        db.add(a3); db.flush()
        s.alerte_id = a3.id
        db.commit()
    finally:
        db.close()


def amorcer_si_vide():
    db = SessionLocal()
    try:
        if db.scalar(func.count(Alerte.id)) == 0:
            db.close()
            reinitialiser_base()
            return
    finally:
        try:
            db.close()
        except Exception:
            pass
