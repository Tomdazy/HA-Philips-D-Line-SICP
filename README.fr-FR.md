# ha-philips-dline-sicp

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Intégration custom Home Assistant pour piloter les moniteurs **Philips D-Line** via le réseau local en utilisant le protocole binaire **SICP** (port TCP 5000).

> Équivalent natif HA du plugin Homebridge [homebridge-philips-dline-sicp](https://github.com/Tomdazy/homebridge-philips-dline-sicp).

---

## Fonctionnalités

| Fonctionnalité | Détail |
|---|---|
| **Alimentation** | Allumer / mettre en veille |
| **Sélection de source** | HDMI 1–4, DisplayPort, VGA, Media Player, Browser, PDF Player… |
| **Volume** | Niveau absolu (0–100), mute/unmute, monter/descendre |
| **Luminosité** | Attribut d'état + service `philips_dline_sicp.set_brightness` |
| **Contraste** | Attribut d'état + service `philips_dline_sicp.set_contrast` |
| **Polling** | Intervalle configurable (0 = désactivé) |
| **Config Flow** | Configuration graphique complète — aucun YAML requis |
| **Options Flow** | Modification des réglages à tout moment sans reconfiguration |
| **Multi-moniteurs** | Ajoutez plusieurs entrées pour plusieurs moniteurs |

---

## Prérequis

- Home Assistant **2024.1** ou version ultérieure
- Un moniteur Philips D-Line avec le contrôle réseau activé :
  - Menu OSD → **Configuration 1 → Network Settings** → activer
  - Vérifier que le port SICP affiche **5000 (Connected)**
  - Relever l'**adresse IP** et le **Monitor ID** du moniteur (OSD → Advanced Option)
- Le moniteur doit être joignable depuis HA sur **TCP port 5000**

> ⚠️ Le protocole SICP ne comporte aucune authentification. Gardez votre moniteur sur un VLAN de confiance ou un segment réseau local isolé.

---

## Installation

### Via HACS (recommandé)

1. Dans HACS, cliquer sur **Dépôts personnalisés**
2. Ajouter l'URL de ce dépôt avec la catégorie **Intégration**
3. Rechercher **"Philips D-Line SICP"** et cliquer sur Installer
4. Redémarrer Home Assistant

### Manuelle

```bash
# Depuis le répertoire de configuration de HA :
cp -r custom_components/philips_dline_sicp /config/custom_components/
```

Redémarrer Home Assistant.

---

## Configuration

1. Aller dans **Paramètres → Appareils et services → Ajouter une intégration**
2. Rechercher **"Philips D-Line"**
3. Remplir les étapes ci-dessous

### Étape 1 — Connexion

| Champ | Défaut | Description |
|---|---|---|
| Adresse IP | — | IP du moniteur sur votre réseau local |
| Port TCP | `5000` | Port SICP (ne pas modifier sauf cas particulier) |
| Monitor ID | `1` | Identifiant OSD du moniteur (OSD → Advanced Option) |
| Group ID | `0` | Octet de groupe (généralement 0) |
| Include Group byte | ✓ | Décocher si aucun ACK n'est reçu |

L'intégration tente une connexion en direct avant d'enregistrer. Si le moniteur ne répond pas, un message d'erreur s'affiche.

### Étape 2 — Options

| Champ | Défaut | Description |
|---|---|---|
| Intervalle de polling | `15` s | Fréquence de mise à jour de l'état (0 = désactivé) |
| Volume minimum | `0` | Borne basse pour la mise à l'échelle du volume |
| Volume maximum | `100` | Borne haute pour la mise à l'échelle du volume |
| Exposer la luminosité | ✓ | Ajoute `brightness` aux attributs d'état de l'entité |
| Exposer le contraste | ✗ | Ajoute `contrast` aux attributs d'état de l'entité |

Tous ces réglages peuvent être modifiés ultérieurement via **Paramètres → Appareils et services → Configurer**, sans supprimer l'intégration.

---

## Sources d'entrée

Les sources sont définies dans `const.py` (`DEFAULT_INPUTS`). Les codes SICP peuvent varier selon la version du firmware — ajustez-les si votre moniteur ne réagit pas à une source particulière.

| Source | Code SICP |
|---|---|
| HDMI 1 | `0x0D` |
| HDMI 2 | `0x06` |
| HDMI 3 | `0x0F` |
| HDMI 4 | `0x19` |
| DisplayPort | `0x22` |
| DVI-D | `0x04` |
| VGA | `0x01` |
| Media Player | `0x30` |
| Browser | `0x40` |
| PDF Player | `0x41` |
| Card OPS | `0x07` |

---

## Services disponibles

### `philips_dline_sicp.set_brightness`

Règle la luminosité de l'écran (0–100).

```yaml
service: philips_dline_sicp.set_brightness
data:
  brightness: 70
```

### `philips_dline_sicp.set_contrast`

Règle le contraste de l'écran (0–100).

```yaml
service: philips_dline_sicp.set_contrast
data:
  contrast: 50
```

---

## Exemples d'automatisation

### Allumer au lever du soleil et sélectionner HDMI 1

```yaml
automation:
  - alias: "Moniteur salon — allumage matin"
    trigger:
      platform: sun
      event: sunrise
    action:
      - service: media_player.turn_on
        target:
          entity_id: media_player.philips_d_line_192_168_1_120
      - delay: "00:00:02"
      - service: media_player.select_source
        target:
          entity_id: media_player.philips_d_line_192_168_1_120
        data:
          source: "HDMI 1"
```

### Réduire la luminosité le soir

```yaml
automation:
  - alias: "Moniteur salon — mode nuit"
    trigger:
      platform: time
      at: "22:00:00"
    action:
      - service: philips_dline_sicp.set_brightness
        data:
          brightness: 20
```

### Couper le son lors d'un appel téléphonique (exemple)

```yaml
automation:
  - alias: "Moniteur — sourdine pendant appel"
    trigger:
      platform: state
      entity_id: binary_sensor.telephone_en_appel
      to: "on"
    action:
      - service: media_player.mute_volume
        target:
          entity_id: media_player.philips_d_line_192_168_1_120
        data:
          is_volume_muted: true
```

---

## Dépannage

| Symptôme | Solution |
|---|---|
| "Cannot connect" lors de la configuration | Vérifier l'IP, que le port 5000 est accessible, et que le contrôle réseau est activé dans l'OSD |
| Pas d'ACK / timeouts répétés | Essayer de désactiver l'octet Group (`Include Group byte = false`) |
| La source ne change pas | Votre firmware utilise peut-être des codes différents — comparez avec la documentation SICP de votre modèle |
| L'entité devient indisponible | Le moniteur est éteint ou injoignable ; l'état se rétablit au prochain polling |

Test rapide de connectivité depuis un terminal :

```bash
nc -zv 192.168.1.120 5000
```

Activer les logs de débogage pour plus de détails :

```yaml
# configuration.yaml
logger:
  logs:
    custom_components.philips_dline_sicp: debug
```

---

## Notes sur le protocole SICP

SICP (Serial/Ethernet Interface Communication Protocol) est un protocole binaire utilisé sur les écrans professionnels Philips. Chaque paquet contient un octet de longueur, l'identifiant du moniteur, un octet de groupe optionnel, un octet de commande, des données optionnelles et un checksum XOR. Le moniteur répond par ACK (succès), NACK (erreur de checksum) ou NAV (commande non supportée par ce firmware).

Cette intégration utilise le cadrage **SICP v2** sur TCP. Si votre moniteur annonce SICP v1.x, essayez de désactiver l'octet de groupe dans les options.

---

## Licence

MIT — voir [LICENSE](LICENSE)
