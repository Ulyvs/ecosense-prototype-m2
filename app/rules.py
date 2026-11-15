"""Contrôles qualité et règles d'alerte. Une valeur inhabituelle est marquée, jamais supprimée."""
from dataclasses import dataclass

PLAGES = {"air": (0.0, 1000.0), "bruit": (0.0, 140.0)}   # PM2.5 en µg/m³ ; LAeq en dB(A)
SEUIL_PM25 = 50.0      # µg/m³
SEUIL_BRUIT = 70.0     # dB(A)
PERSISTANCE = {"air": 3, "bruit": 2}   # nombre de relevés consécutifs requis


def qualite(type_mesure: str, valeur: float) -> str:
    lo, hi = PLAGES[type_mesure]
    return "valide" if lo <= valeur <= hi else "hors_plage"


@dataclass
class Declenchement:
    titre: str
    priorite: str
    action: str
    hypothese: str


def evaluer(type_mesure: str, quartier: str, valeurs_recentes: list[float]) -> Declenchement | None:
    """valeurs_recentes : les derniers relevés valides, du plus ancien au plus récent."""
    n = PERSISTANCE[type_mesure]
    seuil = SEUIL_PM25 if type_mesure == "air" else SEUIL_BRUIT
    if len(valeurs_recentes) < n:
        return None
    derniers = valeurs_recentes[-n:]
    if not all(v > seuil for v in derniers):
        return None
    if type_mesure == "air":
        return Declenchement(
            titre=f"Hausse des PM2.5 — {quartier}",
            priorite="Haute" if max(derniers) >= 70 else "Moyenne",
            action="Vérifier le capteur",
            hypothese="Hausse réelle de la pollution, ou dérive du capteur : à vérifier sur le terrain.",
        )
    return Declenchement(
        titre=f"Bruit élevé — {quartier}",
        priorite="Moyenne",
        action="Renforcer la surveillance",
        hypothese="Nuisance sonore répétée, cause non établie (trafic, chantier, activité).",
    )
