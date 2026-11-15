"""Simulateur de capteurs EcoSense : envoie des relevés à l'API à intervalle régulier.

Usage (serveur lancé sur 127.0.0.1:8000) :
    python scripts/simulateur.py                     # scénario par défaut : PM2.5 à Malabata
    python scripts/simulateur.py --quartier Q-CV --type air --valeurs 40,55,62,71 --pas 3

Utilise uniquement la bibliothèque standard : pas d'installation supplémentaire.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

CLE_CAPTEUR = os.environ.get("ECOSENSE_CAPTEUR_CLE", "capteur-demo-2026")


def envoyer(base, quartier, type_, valeur, unite):
    corps = json.dumps({
        "quartier": quartier, "type": type_, "valeur": valeur, "unite": unite,
        "horodatage": datetime.now(timezone.utc).isoformat(),
    }).encode("utf-8")
    req = urllib.request.Request(f"{base}/api/mesures", data=corps,
                                 headers={"Content-Type": "application/json", "X-Capteur-Cle": CLE_CAPTEUR}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main():
    p = argparse.ArgumentParser(description="Simulateur de capteurs EcoSense")
    p.add_argument("--base", default="http://127.0.0.1:8000", help="adresse du serveur")
    p.add_argument("--quartier", default="Q-MB", help="Q-CV, Q-MB ou Q-BM")
    p.add_argument("--type", default="air", choices=["air", "bruit"])
    p.add_argument("--valeurs", default="42,55,61,68", help="relevés séparés par des virgules")
    p.add_argument("--pas", type=float, default=5.0, help="secondes entre deux relevés")
    a = p.parse_args()

    unite = "µg/m³" if a.type == "air" else "dB(A)"
    valeurs = [float(v) for v in a.valeurs.split(",") if v.strip()]
    print(f"Envoi de {len(valeurs)} relevés ({a.type}, {a.quartier}) toutes les {a.pas} s")
    for v in valeurs:
        try:
            statut, rep = envoyer(a.base, a.quartier, a.type, v, unite)
        except urllib.error.URLError:
            print("Serveur injoignable. Lance-le d'abord : python -m uvicorn app.main:app --reload")
            sys.exit(1)
        if statut == 201:
            alerte = f" → alerte créée : {rep['alerte_creee']}" if rep.get("alerte_creee") else ""
            print(f"  {v} {unite} enregistré ({rep['statut_qualite']}){alerte}")
        else:
            print(f"  {v} {unite} refusé : {rep}")
        time.sleep(a.pas)
    print("Terminé. Actualise la page pour voir la courbe et l'alerte.")


if __name__ == "__main__":
    main()