# EcoSense – prototype (v0.3)
 
Prototype fonctionnel de la plateforme EcoSense : mesures de capteurs, signalements citoyens, alertes,
décision humaine journalisée, suivi citoyen et carte des alertes. Données fictives.
 
Connexion avec comptes de démonstration (mots de passe haché, jeton signé 8 h) :
 
| Compte | Mot de passe | Peut |
|---|---|---|
| (sans connexion) | - | signaler, suivre, consulter la carte et les alertes |
| citoyen | citoyen-demo | comme ci-dessus |
| agent | agent-demo | qualifier un signalement en alerte |
| decideur | decideur-demo | décider sur les alertes, réinitialiser la démonstration |
 
Les capteurs envoient leurs relevés avec l'en-tête `X-Capteur-Cle` (clé de démonstration : `capteur-demo-2026`).
Variables d'environnement : `ECOSENSE_SECRET` (secret des jetons) et `ECOSENSE_CAPTEUR_CLE`.
 
## Installation et lancement
 
Sous Windows (PowerShell), dans le dossier du projet :
 
    py -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    python -m uvicorn app.main:app --reload
 
Puis ouvrir http://127.0.0.1:8000/
 
Sous macOS / Linux : remplacer `py` par `python3` et `.venv\Scripts\Activate.ps1` par `source .venv/bin/activate`.
 
Si Windows bloque les fichiers compilés de SQLAlchemy (« Application Control policy »), supprimer les `.pyd`
de SQLAlchemy dans le venv : `Get-ChildItem .venv\Lib\site-packages\sqlalchemy -Recurse -Filter "*.pyd" | Remove-Item`.
SQLAlchemy utilise alors sa version Python, plus lente mais suffisante pour ce prototype.
 
## Premier lancement après mise à jour
 
La base a changé (colonne `auteur`). Supprime le dossier `data` avant de relancer : `Remove-Item -Recurse data`.
 
## Ce que l'on peut faire sur la page
 
- **Signaler une nuisance** (rôle Citoyen) : le signalement reçoit une référence et reste « Reçu ».
- **Suivre mon signalement** : saisir la référence (ex. SIG-2026-0041) pour voir l'avancement. La description n'est pas affichée.
- **Qualifier en alerte** (rôle Agent) : transforme un signalement en alerte.
- **Décider** (rôle Décideur) : fait passer une alerte à l'étape suivante, avec un motif de 10 caractères minimum. Chaque décision est journalisée.
- **Courbe des relevés** : dans la fiche d'une alerte, évolution des mesures avec le seuil.
- **Carte des alertes** : positions approximatives des quartiers, couleur selon la priorité.
## Simulateur de capteurs
 
Pendant que le serveur tourne, dans un second terminal :
 
    python scripts\simulateur.py
    python scripts\simulateur.py --quartier Q-CV --valeurs 40,55,62,71 --pas 3
 
Options : `--quartier` (Q-CV, Q-MB, Q-BM), `--type` (air ou bruit), `--valeurs`, `--pas` (secondes entre deux relevés).
 
## Règles d'alerte
 
- Air (PM2.5) : 3 relevés consécutifs au-dessus de 50 µg/m³ déclenchent une alerte. Priorité haute à partir de 70.
- Bruit : 2 relevés consécutifs au-dessus de 70 dB(A) déclenchent une alerte.
- Une valeur hors plage (air entre 0 et 1000 µg/m³, bruit entre 0 et 140 dB(A)) est marquée, jamais supprimée.
- Une seule alerte ouverte à la fois par quartier et par type.
Ces seuils sont indicatifs : ils doivent être validés avec les normes retenues dans le cahier des charges.
 
## Tests
 
    python -m pytest -q tests
 
13 tests : connexion, jeton falsifié, rôles, clé capteur, motif obligatoire, déclenchement d'alerte, suivi, carte.
 
## Structure
 
- `app/models.py` : mesures, signalements, alertes, journal de décisions (SQLAlchemy)
- `app/rules.py` : contrôle de plage et règles de persistance
- `app/workflow.py` : états d'une alerte et rôles autorisés
- `app/main.py` : API REST principale
- `app/extensions.py` : suivi citoyen, données de la carte, pages `/suivi` et `/carte`
- `app/seed.py` : scénarios de démonstration
- `static/index.html` : interface principale (signalement, suivi, alertes, carte, courbe)
- `scripts/simulateur.py` : envoi de relevés de capteurs
- `tests/` : tests automatisés
## Limites assumées
 
- Capteurs simulés ; aucune donnée réelle.
- Positions des quartiers : points de repère, pas des limites officielles.
- Aucune authentification ni chiffrement : ne pas exposer tel quel sur Internet.
- SQLite par défaut ; variable `ECOSENSE_DB` pour utiliser PostgreSQL.
 