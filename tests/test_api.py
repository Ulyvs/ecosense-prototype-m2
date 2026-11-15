import os
os.environ["ECOSENSE_DB"] = "sqlite:///./data/test.db"

from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
CAPTEUR = {"X-Capteur-Cle": "capteur-demo-2026"}
MOTS = {"citoyen": "citoyen-demo", "agent": "agent-demo", "decideur": "decideur-demo"}


def connecter(compte):
    r = client.post("/api/connexion", json={"compte": compte, "mot_de_passe": MOTS[compte]})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['jeton']}"}


def reinitialiser():
    client.post("/api/demo/reinitialiser", headers=connecter("decideur"))


def test_mauvais_mot_de_passe_refuse():
    r = client.post("/api/connexion", json={"compte": "decideur", "mot_de_passe": "faux"})
    assert r.status_code == 401


def test_jeton_falsifie_refuse():
    jeton = client.post("/api/connexion", json={"compte": "citoyen", "mot_de_passe": "citoyen-demo"}).json()["jeton"]
    corps, signature = jeton.split(".")
    import base64, json
    charge = json.loads(base64.urlsafe_b64decode(corps))
    charge["r"] = "decideur"  # le citoyen tente de se donner le rôle décideur
    falsifie = base64.urlsafe_b64encode(json.dumps(charge).encode()).decode()
    r = client.get("/api/alertes", headers={"Authorization": f"Bearer {falsifie}.{signature}"})
    assert r.status_code == 401


def test_role_lu_dans_le_jeton():
    assert client.get("/api/moi", headers=connecter("agent")).json()["role"] == "agent"
    assert client.get("/api/moi").json()["role"] == "citoyen"


def test_citoyen_ne_peut_pas_decider():
    reinitialiser()
    alertes = client.get("/api/alertes", headers=connecter("decideur")).json()
    r = client.post(f"/api/alertes/{alertes[0]['id']}/decisions",
                    json={"action": "x", "motif": "motif suffisant"}, headers=connecter("citoyen"))
    assert r.status_code == 403


def test_decision_journalisee_avec_auteur():
    reinitialiser()
    alertes = client.get("/api/alertes", headers=connecter("decideur")).json()
    a = next(x for x in alertes if x["reference"] == "AL-2026-001")
    assert client.post(f"/api/alertes/{a['id']}/decisions", json={"action": "x", "motif": "court"},
                       headers=connecter("decideur")).status_code == 422
    r = client.post(f"/api/alertes/{a['id']}/decisions",
                    json={"action": "x", "motif": "Capteur vérifié sur place, valeurs cohérentes."},
                    headers=connecter("decideur"))
    assert r.status_code == 200
    assert r.json()["statut"] == "Clôturée"
    assert r.json()["journal"][-1]["auteur"] == "decideur"


def test_signalement_qualifie_seulement_par_agent():
    reinitialiser()
    ref = client.post("/api/signalements", json={
        "type": "visuel", "quartier": "Q-MB", "lieu": "Rue du marché",
        "description": "Sacs de déchets laissés sur le trottoir depuis deux jours."}).json()["reference"]
    assert client.post(f"/api/signalements/{ref}/qualifier", headers=connecter("citoyen")).status_code == 403
    q = client.post(f"/api/signalements/{ref}/qualifier", headers=connecter("agent"))
    assert q.status_code == 200 and q.json()["alerte"].startswith("AL-")


def test_capteur_sans_cle_refuse():
    r = client.post("/api/mesures", json={"quartier": "Q-CV", "type": "air", "valeur": 40, "unite": "µg/m³",
                                          "horodatage": "2026-11-15T10:00:00+00:00"})
    assert r.status_code == 401


def test_cinq_releves_creent_une_alerte_et_mauvaise_valeur_marquee():
    reinitialiser()
    t0 = datetime(2026, 11, 14, 10, tzinfo=timezone.utc)
    creee = None
    for i, v in enumerate([55, 58, 61]):
        r = client.post("/api/mesures", headers=CAPTEUR, json={
            "quartier": "Q-BM", "type": "air", "valeur": v, "unite": "µg/m³",
            "horodatage": (t0 + timedelta(hours=i)).isoformat()})
        assert r.status_code == 201
        creee = r.json()["alerte_creee"] or creee
    assert creee is not None
    bad = client.post("/api/mesures", headers=CAPTEUR, json={
        "quartier": "Q-BM", "type": "air", "valeur": -5, "unite": "µg/m³",
        "horodatage": (t0 + timedelta(hours=9)).isoformat()})
    assert bad.json()["statut_qualite"] == "hors_plage"


def test_reinitialisation_reservee_au_decideur():
    assert client.post("/api/demo/reinitialiser", headers=connecter("agent")).status_code == 403