# ha-philips-dline-sicp

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

🇬🇧 [English version](README.md)

Intégration Home Assistant pour piloter les moniteurs professionnels **Philips** (gamme D-Line et autres modèles Signage) sur le réseau local, via le protocole **SICP** (port TCP 5000), selon la spécification SICP 2.09.

Le moniteur apparaît comme une **télévision** : HomeKit Bridge l'expose dans l'app Maison sous forme d'accessoire Téléviseur, avec l'alimentation, les entrées, le volume et la télécommande de l'iPhone.

---

## Ce qui est pilotable

Les entités marquées ◌ sont **désactivées par défaut** : peu de modèles les supportent, ou elles servent rarement. On les active depuis la fiche de l'appareil (*Paramètres → Appareils et services → Philips D-Line → entités masquées*).

| Plateforme | Entités |
|---|---|
| **Télévision** (`media_player`) | Marche / veille, choix de la source, volume des haut-parleurs, sourdine |
| **Rétroéclairage** (`light`) | Allumer ou éteindre la dalle sans couper l'électronique, luminosité. Dans HomeKit, c'est une ampoule variable. |
| **Réglages** (`number`) | Luminosité, couleur, contraste, netteté, teinte ◌, niveau de noir ◌, volume de la sortie audio ◌, aigus ◌, graves ◌, température de couleur en kelvins ◌, gains et décalages RVB ◌, limites de volume ◌, durée de l'OSD d'information ◌, minuterie d'arrêt, délai d'allumage ◌ |
| **Modes** (`select`) | Format d'image, style d'image, gamma, température de couleur, état à la mise sous tension, détection auto du signal, Smart power, mode ECO, HDMI CEC, verrouillage télécommande, verrouillage clavier. Désactivés par défaut : réduction du bruit, MEMC, mode de balayage, conversion de balayage, plage HDMI, mire de test, calibration couleur d'usine, orientation, source au démarrage, mode d'économie d'énergie, APM, décalage des pixels, capteur de présence, ventilateur, logo au démarrage, tactile, barre de navigation, alimentation OPS/SDM, port de contrôle réseau, langue de l'OSD, fuseau horaire |
| **Interrupteurs** (`switch`) | Figer l'image, coupure A/V, haut-parleurs internes, voyant d'alimentation, Wake on LAN, verrouillage USB / microSD. Désactivés par défaut : synchro audio, capteur de luminosité, rotation de l'OSD, synchro automatique de l'heure, TeamViewer, relance forcée de l'app personnalisée, redémarrage automatique |
| **Heures** (`time`) | Heure du redémarrage automatique ◌, horloge du moniteur ◌ |
| **Capteurs** (`sensor`) | Température, heures de fonctionnement, modèle, version du firmware, firmware Android, version SICP, numéro de série. Désactivés par défaut : date de compilation, plateforme, firmwares du switch HDMI et du module LAN |
| **Capteur binaire** | Signal vidéo présent |
| **Boutons** (`button`) | Redémarrer. Désactivés par défaut : capture d'écran par e-mail, menu admin Android, réglage auto VGA, chaîne +/−, réinitialisation des programmations, réinitialisation d'usine |

Une commande que votre moniteur ne connaît pas (réponse NACK, ou NAV répétés) rend l'entité *indisponible*. L'intégration la réessaie une heure plus tard.

La liste des sources est lue sur le moniteur (commande `0xAB`, SICP 2.05 et plus). À défaut, on la choisit dans le catalogue complet.

---

## Prérequis

- Home Assistant **2024.1** ou plus récent
- Un moniteur Philips avec le contrôle réseau activé :
  - menu OSD → **Configuration 1 → Paramètres réseau** : activer le réseau
  - vérifier que le port SICP indique **5000**
  - relever l'**adresse IP** et le **Monitor ID** (OSD → Option avancée)
- Le port **TCP 5000** du moniteur doit être joignable depuis Home Assistant
- Pour que la mise en marche fonctionne à distance, le moniteur doit garder le réseau actif en veille : réglez **APM / mode ECO** en conséquence (voir le manuel du moniteur)

> ⚠️ SICP n'a aucune authentification : gardez le moniteur sur un réseau de confiance.

---

## Installation

### Via HACS (recommandé)

1. Dans HACS, ouvrez **Dépôts personnalisés**
2. Ajoutez l'URL de ce dépôt, catégorie **Intégration**
3. Installez **Philips D-Line SICP**
4. Redémarrez Home Assistant

### Manuelle

```bash
cp -r custom_components/philips_dline_sicp /config/custom_components/
```

Puis redémarrez Home Assistant.

---

## Configuration

*Paramètres → Appareils et services → Ajouter une intégration → Philips D-Line*

### Étape 1 : connexion

| Champ | Défaut | Rôle |
|---|---|---|
| Adresse IP | — | IP du moniteur |
| Port TCP | `5000` | Port SICP |
| Monitor ID | `1` | Identifiant défini dans l'OSD |
| Group ID | `0` | `0` = pilotage par Monitor ID |
| Inclure l'octet Group | ✓ | À décocher uniquement pour de très vieux firmwares (SICP 1.x) |

L'intégration teste la connexion avant d'enregistrer.

### Étape 2 : options (modifiables ensuite via **Configurer**)

| Champ | Défaut | Rôle |
|---|---|---|
| Entrées | sources annoncées par le moniteur | Sources proposées dans Home Assistant et HomeKit |
| Rafraîchissement de l'état | `15` s | Alimentation, source, volume, image (0 = désactivé) |
| Rafraîchissement des réglages | `300` s | Tous les autres réglages |
| Volume minimum / maximum | `0` / `100` | Bornes du curseur de volume |
| Pas du volume | `2` | Incrément des boutons volume + / − |

En veille, seule l'alimentation est interrogée : le moniteur refuse la plupart des autres commandes dans cet état.

---

## HomeKit : le moniteur comme téléviseur

HomeKit n'accepte les téléviseurs que comme **accessoires indépendants**, pas derrière un pont. Home Assistant s'en charge automatiquement :

1. *Paramètres → Appareils et services → Ajouter une intégration → **HomeKit Bridge***
2. Cochez au moins le domaine **Lecteur multimédia** (ajoutez **Lumière** et **Interrupteur** pour la luminosité et les interrupteurs), puis validez
3. Home Assistant crée le pont, **plus une instance dédiée en mode accessoire pour le téléviseur**. Chacune affiche un QR code d'appairage dans les notifications.
4. Dans l'app Maison : **Ajouter un accessoire**, puis scannez le QR code du téléviseur (et celui du pont si vous l'utilisez)

Si HomeKit Bridge est déjà configuré, ajoutez une entrée HomeKit Bridge en **mode accessoire** (options : *Mode* `accessory`, *Entité* `media_player.philips_…`).

Vous obtenez alors dans l'app Maison :

- l'allumage et la mise en veille
- les **entrées**, avec leurs noms (renommables et masquables dans l'app)
- le **volume** et la **sourdine** depuis la télécommande du Centre de contrôle, via les boutons physiques de l'iPhone

Via le pont, le **rétroéclairage** apparaît comme une ampoule variable (luminosité de l'écran) et les **interrupteurs** (figer l'image, coupure A/V…) comme des prises. Pensez à filtrer les entités exposées dans les options du pont.

> Les flèches de la télécommande iOS n'ont pas d'équivalent SICP. Home Assistant émet toutefois l'événement `homekit_tv_remote_key_pressed` : vous pouvez l'utiliser dans vos automatisations.

---

## Services

### `philips_dline_sicp.select_source_playlist`

Bascule sur Media Player, PDF Player ou Browser et lance une playlist ou une URL (1 à 7, 8 = lecture auto USB).

```yaml
action: philips_dline_sicp.select_source_playlist
target:
  entity_id: media_player.philips_43bdl4550d_00
data:
  source: Media Player
  playlist: 2
```

### `philips_dline_sicp.set_brightness` / `set_contrast`

Conservés pour compatibilité. Préférez les entités `number` correspondantes.

```yaml
action: philips_dline_sicp.set_brightness
target:
  entity_id: media_player.philips_43bdl4550d_00
data:
  brightness: 70
```

### `philips_dline_sicp.send_raw_command`

Diagnostic : envoie une commande SICP brute et **retourne** la réponse (dans *Outils de développement → Actions*, cochez « Retourner une réponse »).

```yaml
action: philips_dline_sicp.send_raw_command
data:
  cmd: "0xA2"
  data: "00"
```

---

## Exemples d'automatisations

### Allumer à 8 h sur HDMI 1

```yaml
automation:
  - alias: Moniteur, allumage du matin
    triggers:
      - trigger: time
        at: "08:00:00"
    actions:
      - action: media_player.turn_on
        target:
          entity_id: media_player.philips_43bdl4550d_00
      - delay: "00:00:05"
      - action: media_player.select_source
        target:
          entity_id: media_player.philips_43bdl4550d_00
        data:
          source: HDMI 1
```

### Baisser la luminosité le soir

```yaml
automation:
  - alias: Moniteur, luminosité réduite
    triggers:
      - trigger: time
        at: "20:00:00"
    actions:
      - action: number.set_value
        target:
          entity_id: number.philips_43bdl4550d_00_luminosite
        data:
          value: 30
```

---

## Dépannage

| Symptôme | Piste |
|---|---|
| « Impossible de joindre le moniteur » | Vérifiez l'IP, le port 5000 (`nc -zv <ip> 5000`) et le contrôle réseau dans l'OSD |
| La mise en marche ne fonctionne pas | Réglez APM / mode ECO pour que le réseau reste actif en veille |
| Une entité reste indisponible | Votre modèle ne supporte pas la commande. Désactivez l'entité. |
| Les réglages d'image sont indisponibles sur une source Android | Normal sur certains modèles (BDL3452T, BDL3651T, BDL3550Q, BDL4550D) : SICP n'y règle l'image que sur les sources externes |
| Aucune réponse du tout | Essayez de décocher « Inclure l'octet Group » (très vieux firmwares) |

Journaux détaillés :

```yaml
logger:
  logs:
    custom_components.philips_dline_sicp: debug
```

---

## Contribuer

Voir [CONTRIBUTING.md](CONTRIBUTING.md). L'historique des versions est dans [CHANGELOG.md](CHANGELOG.md).

## Licence

MIT, voir [LICENSE](LICENSE).
