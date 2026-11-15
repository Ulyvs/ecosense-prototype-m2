"""Authentification du prototype : comptes avec mot de passe haché, jetons signés, clé pour les capteurs.

Bibliothèque standard uniquement. Les mots de passe de démonstration sont dans le code :
ne jamais reprendre ce module tel quel en production (secret, comptes et mots de passe à externaliser).
"""
import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import HTTPException

SECRET = os.environ.get("ECOSENSE_SECRET", "secret-de-demonstration").encode("utf-8")
CLE_CAPTEUR = os.environ.get("ECOSENSE_CAPTEUR_CLE", "capteur-demo-2026")
DUREE_SESSION = 8 * 3600  # secondes

COMPTES = {
    "citoyen": {"nom": "Citoyen", "role": "citoyen"},
    "agent": {"nom": "Agent municipal", "role": "agent"},
    "decideur": {"nom": "Décideur", "role": "decideur"},
}
# Mots de passe de démonstration, affichés dans l'interface et dans le README.
_MOTS_DE_DEMO = {"citoyen": "citoyen-demo", "agent": "agent-demo", "decideur": "decideur-demo"}


def _empreinte(mot: str, sel: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", mot.encode("utf-8"), sel, 200_000).hex()


_SELS = {compte: b"ecosense-" + compte.encode() for compte in COMPTES}
_EMPREINTES = {compte: _empreinte(_MOTS_DE_DEMO[compte], _SELS[compte]) for compte in COMPTES}


def verifier_mot_de_passe(compte: str, mot: str) -> bool:
    if compte not in COMPTES:
        return False
    return hmac.compare_digest(_empreinte(mot, _SELS[compte]), _EMPREINTES[compte])


def _signature(corps: str) -> str:
    return hmac.new(SECRET, corps.encode("utf-8"), hashlib.sha256).hexdigest()


def emettre_jeton(compte: str) -> str:
    charge = json.dumps({"c": compte, "r": COMPTES[compte]["role"], "e": int(time.time()) + DUREE_SESSION})
    corps = base64.urlsafe_b64encode(charge.encode("utf-8")).decode("ascii")
    return f"{corps}.{_signature(corps)}"


def lire_jeton(jeton: str):
    try:
        corps, signature = jeton.split(".")
    except ValueError:
        raise HTTPException(401, "Jeton invalide")
    if not hmac.compare_digest(signature, _signature(corps)):
        raise HTTPException(401, "Jeton invalide")
    try:
        charge = json.loads(base64.urlsafe_b64decode(corps.encode("ascii")))
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(401, "Jeton invalide")
    if charge["e"] < time.time():
        raise HTTPException(401, "Session expirée, reconnectez-vous")
    return charge["c"], charge["r"]


def identite(authorization: str | None):
    """Renvoie (compte, rôle). Sans jeton : visiteur public, rôle citoyen."""
    if not authorization or not authorization.startswith("Bearer "):
        return "public", "citoyen"
    return lire_jeton(authorization[len("Bearer "):].strip())


def exiger_capteur(cle: str | None) -> None:
    if cle != CLE_CAPTEUR:
        raise HTTPException(401, "Clé capteur absente ou invalide")