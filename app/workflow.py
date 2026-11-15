"""Machine à états des alertes et permissions par rôle (partie 8 : décision humaine obligatoire)."""

ROLES = {"citoyen", "agent", "decideur"}

TRANSITIONS = {
    "Créée":            {"suivant": "En qualification", "roles": {"agent"}},
    "En qualification": {"suivant": "À valider",        "roles": {"agent"}},
    "À valider":        {"suivant": "Clôturée",         "roles": {"decideur"}},
}


def transition_possible(statut: str, role: str):
    """Renvoie l'état suivant si le rôle est autorisé, sinon None."""
    t = TRANSITIONS.get(statut)
    if t and role in t["roles"]:
        return t["suivant"]
    return None


def actions_permises(statut: str, role: str) -> list[str]:
    return [statut] if transition_possible(statut, role) else []
