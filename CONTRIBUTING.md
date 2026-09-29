# Contribuer

Merci de votre intérêt pour l'intégration ! Ce guide explique comment préparer un environnement, ajouter une commande SICP et proposer une modification.

## Préparer l'environnement

```bash
git clone https://github.com/Tomdazy/ha-philips-dline-sicp.git
cd ha-philips-dline-sicp

# Hook de commit du dépôt (une fois par clone)
git config core.hooksPath .githooks

# Environnement de test (Python 3.12)
python3 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
```

## Lancer les tests

```bash
.venv/bin/python -m pytest
```

Les tests démarrent un **faux moniteur SICP** (`tests/fake_monitor.py`) sur un port local. Ils couvrent le framing, les réponses ACK / NAV / NACK, les entités, les actions et l'exposition de la télévision à HomeKit. Aucun moniteur réel n'est nécessaire.

Avant d'ouvrir une pull request, testez aussi sur un vrai moniteur si possible, avec les journaux en `debug`, et indiquez le modèle et la version SICP (capteur « Version SICP ») dans la PR.

## Organisation du code

```
custom_components/philips_dline_sicp/
├── sicp.py            client TCP : framing, ACK/NAV/NACK, reconnexion
├── coordinator.py     polling : rythmes rapide / lent / statique, commandes non supportées
├── descriptions.py    catalogue déclaratif des commandes exposées en entités
├── entity.py          classes de base (fiche appareil, disponibilité, construction des trames)
├── media_player.py    la télévision (source, volume, sourdine, actions d'entité)
├── light.py           rétroéclairage
├── number.py / select.py / switch.py / sensor.py / binary_sensor.py / button.py / time.py
├── config_flow.py     configuration et options
├── strings.json       textes de référence (anglais)
└── translations/      en.json (copie de strings.json), fr.json
```

La référence du protocole est la spécification **SICP 2.09** de Philips / TPV (« The SICP Commands Document »).

## Ajouter une commande SICP

La plupart des commandes se résument à une paire Get / Set ; il suffit alors de la déclarer.

1. Ajoutez une description dans le tuple adéquat de `descriptions.py` (`NUMBERS`, `SELECTS`, `SWITCHES`, `SENSORS`, `BUTTONS`…). On y indique :
   - `get_cmd` / `get_data` : la requête de lecture
   - `set_cmd` : la commande d'écriture
   - `index` : la position de la valeur dans la réponse (DATA[1] = index 0)
   - `frame_len` et `fill` : quand le Set regroupe plusieurs paramètres. La trame est reconstruite depuis la dernière lecture ; `fill=0xFF` signifie « inchangé ».
   - `tier` : `TIER_FAST` pour ce qui change souvent, `TIER_SLOW` pour un réglage, `TIER_STATIC` pour une information fixe
   - `entity_registry_enabled_default=False` si peu de modèles supportent la commande
2. Ajoutez le nom de l'entité et, pour un `select`, le libellé de chaque option dans :
   - `strings.json` et `translations/en.json` (identiques, en anglais)
   - `translations/fr.json`
3. Ajoutez un cas au faux moniteur et un test si la commande a un format particulier.

Les clés d'option d'un `select` sont en minuscules, avec des tirets bas (`[a-z0-9_]`).

## Style de code

- Python 3.12, annotations de type, `from __future__ import annotations`.
- Commentaires et docstrings en français, noms de code en anglais, comme dans le reste du projet.
- Pas de dépendance externe : l'intégration n'utilise que la bibliothèque standard et Home Assistant.

## Commits

- Format [Conventional Commits](https://www.conventionalcommits.org/fr/), **en français** : `feat: …`, `fix: …`, `docs: …`, `refactor: …`, `test: …`, `chore: …`. Le préfixe suit la nature du changement : un correctif est un `fix:`.
- Aucune attribution à une IA dans les messages de commit ni dans les descriptions de PR. Le hook `.githooks/commit-msg` refuse ces messages ; vérifiez l'historique avec `.githooks/commit-msg --history`.

## Publier une version

1. Mettez à jour `version` dans `custom_components/philips_dline_sicp/manifest.json`.
2. Déplacez les entrées « non publiée » de `CHANGELOG.md` sous le nouveau numéro, avec la date.
3. Commitez, puis créez et poussez le tag :

   ```bash
   git commit -am "chore: version 2.0.0"
   git tag v2.0.0
   git push origin main v2.0.0
   ```
