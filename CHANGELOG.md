# Changelog

Toutes les évolutions notables de l'intégration sont consignées ici.
Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), versions selon [SemVer](https://semver.org/lang/fr/).

## [2.0.2] - 2026-09-30

### Corrigé

- Marche et arrêt se reflètent immédiatement : l'état demandé s'affiche tout de suite, puis l'alimentation est relue chaque seconde jusqu'à confirmation par le moniteur (60 s au plus). Avant, la télévision repassait à « éteinte » pendant le démarrage et il fallait attendre le cycle suivant.
- Après un allumage (commande, télécommande ou réveil), toutes les informations sont relues toutes les 2 s pendant 30 s, réglages lents compris. Une commande refusée pendant le démarrage est retentée au passage suivant.
- Un allumage à la télécommande est détecté en 5 s au plus : l'alimentation est désormais relue toutes les 5 s, indépendamment de l'intervalle d'état.
- Allumer le rétroéclairage sur un écran en veille allume l'écran sans envoyer d'autre commande pendant son démarrage.
- Logo et icône conformes au format Home Assistant (transparence, recadrage, 256 px et variantes `@2x` en 512 px pour les écrans haute densité). Home Assistant 2026.3 ou plus récent est nécessaire pour les images locales.

## [2.0.1] - 2026-09-30

### Corrigé

- L'intégration démarre même si le moniteur ne répond pas. Certains modèles (55BDL4511D notamment) coupent leur service SICP en veille tout en gardant le réseau actif. Avant, l'entrée restait bloquée sur « Échec de la configuration » et la télévision disparaissait de HomeKit.
- La télévision reste disponible et s'affiche « éteinte » quand le moniteur ne répond pas : HomeKit peut toujours la rallumer.
- Lecture des trames resynchronisée sur le Monitor ID et le checksum. Les octets orphelins et les réponses en retard (que ces moniteurs livrent parfois sur une autre connexion) sont ignorés, et le tampon est purgé avant chaque commande.

### Ajouté

- Allumage par **Wake on LAN** quand la commande SICP reste sans réponse. L'adresse MAC est détectée automatiquement (table ARP) ou se saisit dans les options.
- Modèle, firmware, numéro de série et liste des entrées sont mémorisés dans l'entrée de configuration : la fiche appareil et les entrées HomeKit restent stables même si Home Assistant redémarre pendant la veille du moniteur.

## [2.0.0] - 2026-09-29

Réécriture complète d'après la spécification **SICP 2.09**.

### ⚠️ Changements incompatibles

- Les attributs `brightness` et `contrast` du `media_player` disparaissent : ils sont remplacés par des entités `number`. Les options « Exposer la luminosité / le contraste » sont supprimées.
- `set_brightness` et `set_contrast` deviennent des actions d'entité : elles exigent désormais une cible `media_player`.
- La liste d'entrées enregistrée par les versions 1.x est ignorée, car ses codes étaient faux. Les entrées se choisissent maintenant dans les options.
- Le nom de l'appareil devient « Philips <modèle> » (ex. « Philips 43BDL4550D/00 »). Les nouvelles entités sont nommées en conséquence ; l'entité `media_player` existante garde son identifiant.

### Ajouté

- Le moniteur est déclaré comme **télévision** (`device_class: tv`) : HomeKit Bridge l'expose en accessoire Téléviseur avec l'alimentation, les entrées, le volume et la sourdine.
- Lecture de la **liste des entrées** du moniteur (`0xAB`), à cocher dans les options.
- Plateforme `light` **Rétroéclairage** : marche/arrêt de la dalle et luminosité (ampoule variable dans HomeKit).
- Plateforme `number` : couleur, contraste, netteté, teinte, niveau de noir, volume de la sortie audio, aigus, graves, température de couleur en kelvins, gains et décalages RVB, limites de volume, durée de l'OSD, minuterie d'arrêt, délai d'allumage.
- Plateforme `select` : 32 réglages, dont format et style d'image, gamma, température de couleur, état à la mise sous tension, détection du signal, modes d'économie d'énergie, HDMI CEC, verrouillages, orientation, langue de l'OSD et fuseau horaire.
- Plateforme `switch` : figer l'image, coupure A/V, haut-parleurs, voyant, Wake on LAN, verrouillage USB/microSD, redémarrage automatique…
- Plateforme `time` : heure du redémarrage automatique, horloge du moniteur.
- Capteurs de température et d'heures de fonctionnement, capteurs de diagnostic (modèle, firmwares, version SICP, n° de série) et capteur binaire « signal vidéo ».
- Plateforme `button` : redémarrage, capture d'écran, menu admin, réglage auto VGA, chaîne +/−, réinitialisations.
- Action `select_source_playlist` : ouvre Media Player, PDF Player ou Browser sur une playlist ou une URL.
- Fiche appareil renseignée (modèle, firmware, plateforme, numéro de série).
- Traduction française (`translations/fr.json`) ; `en.json` est désormais en anglais.
- Suite de tests `pytest` avec un faux moniteur SICP, dont une vérification de l'accessoire Téléviseur HomeKit.

### Corrigé

- Sourdine lue avec `0x46` au lieu de `0xAB` (qui renvoie la liste des sources).
- Contraste lu dans la réponse de `0x33` (DATA[3]) au lieu de `0x13` ; `0x12` et `0x13` concernent la température de couleur.
- `0x32` (paramètres vidéo) envoyé avec ses 7 octets : régler la luminosité n'écrase plus les autres paramètres.
- `0x44` (volume) envoyé avec ses 2 octets, la sortie audio restant inchangée (`0xFF`). Repli sur 1 octet pour les plateformes Eagle et Himalaya 1.x.
- `0xAC` (source) envoyé avec ses 4 octets.
- Codes de source corrigés : DisplayPort `0x0A` (et non `0x22`), VGA `0x05` (et non `0x01`), Media Player `0x16` (et non `0x30`).
- Les réponses ACK, NAV et NACK sont vérifiées : une commande refusée remonte une erreur au lieu d'échouer en silence.
- Lecture des trames selon l'octet MsgSize (plus de lectures tronquées ou fusionnées). Les réponses en retard sont ignorées, et la connexion est rouverte si le moniteur la ferme.

### Modifié

- Polling en deux rythmes : l'état (alimentation, source, volume, image) toutes les 15 s, les autres réglages toutes les 5 min. En veille, seule l'alimentation est interrogée.
- Chaque commande Get n'est envoyée qu'une fois par cycle, même si plusieurs entités en dépendent.
- Une commande non supportée est mise en pause une heure au lieu d'être réessayée à chaque cycle.
- `send_raw_command` retourne la réponse du moniteur (action avec réponse) et accepte un filtre `host`.

## [1.0.4] - 2026-05-02

- Même contenu que 1.0.3.

## [1.0.3] - 2026-05-02

- Journalisation détaillée du polling ; pas du curseur de volume ramené à 2 unités.
- Allumage automatique avant une commande de volume ou de source.

## [1.0.2] - 2026-05-02

- Correction du numéro de version.

## [1.0.1] - 2026-05-02

- Connexion TCP persistante, sérialisée par un verrou, avec reconnexion automatique.

## [0.1.5] - 2026-05-02

- Action de diagnostic `send_raw_command`.

## [0.1.2] / [0.1.3] - 2026-05-02

- Premières corrections des commandes ; icône et logo.

## [0.1.1] - 2026-05-02

- Correction de syntaxe.

## [0.1.0] - 2026-05-02

- Version initiale : alimentation, source, volume, sourdine, luminosité et contraste en attributs.

[2.0.2]: https://github.com/Tomdazy/ha-philips-dline-sicp/compare/v2.0.1...v2.0.2
[2.0.1]: https://github.com/Tomdazy/ha-philips-dline-sicp/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/Tomdazy/ha-philips-dline-sicp/compare/v1.0.4...v2.0.0
[1.0.4]: https://github.com/Tomdazy/ha-philips-dline-sicp/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/Tomdazy/ha-philips-dline-sicp/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/Tomdazy/ha-philips-dline-sicp/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/Tomdazy/ha-philips-dline-sicp/compare/v0.1.5...v1.0.1
[0.1.5]: https://github.com/Tomdazy/ha-philips-dline-sicp/compare/v0.1.3...v0.1.5
[0.1.2]: https://github.com/Tomdazy/ha-philips-dline-sicp/compare/v0.1.1...v0.1.2
[0.1.3]: https://github.com/Tomdazy/ha-philips-dline-sicp/compare/v0.1.2...v0.1.3
[0.1.1]: https://github.com/Tomdazy/ha-philips-dline-sicp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Tomdazy/ha-philips-dline-sicp/releases/tag/v0.1.0
