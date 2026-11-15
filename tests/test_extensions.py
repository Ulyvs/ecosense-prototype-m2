import os
os.environ["ECOSENSE_DB"] = "sqlite:///./data/test.db"

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
MOTS = {"agent": "agent-demo", "decideur": "decideur-demo"}


def connecter(compte):
    r = client.post("/api/connexion", json={"compte": compte, "mot_de_passe": MOTS[compte]})
    return {"Authorization": f"Bearer {r.json()['jeton']}"}


def reinitialiser():
    client.post("/api/demo/reinitialiser", headers=connecter("decideur"))


def test_suivi_suit_le_signalement():
    reinitialiser()
    ref = client.post("/api/signalements", json={
        "type": "visuel", "quartier": "Q-MB", "lieu": "Rue du marché",
        "description": "Sacs de déchets laissés sur le trottoir depuis deux jours."}).json()["reference"]
    avant = client.get(f"/api/suivi/{ref}").json()
    assert [e["atteinte"] for e in avant["etapes"]] == [True, False, False]
    client.post(f"/api/signalements/{ref}/qualifier", headers=connecter("agent"))
    apres = client.get(f"/api/suivi/{ref.lower()}").json()
    assert [e["atteinte"] for e in apres["etapes"]] == [True, True, True]


def test_suivi_reference_inconnue():
    assert client.get("/api/suivi/SIG-0000-0000").status_code == 404


def test_suivi_sans_description():
    reinitialiser()
    assert "description" not in client.get("/api/suivi/SIG-2026-0041").json()


def test_carte_et_pages():
    reinitialiser()
    points = client.get("/api/carte").json()
    assert len(points) == 3 and all(p["lat"] is not None for p in points)
    assert client.get("/suivi").status_code == 200
    assert client.get("/carte").status_code == 200