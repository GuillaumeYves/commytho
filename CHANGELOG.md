# Journal des versions

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et les
numéros suivent [SemVer](https://semver.org/lang/fr/).

## [Non publié]

## [1.0.1] - 2026-09-14

### Ajouté

- `commytho up --rattrapage N` : nombre de créneaux en retard rejoués à chaque
  réveil, `0` pour rattraper tout le programme manqué. La valeur par défaut
  reste 1, soit le comportement historique.
- Windows : la tâche porte un second déclencheur, l'ouverture de session, pour
  que le rattrapage parte au démarrage sans attendre le réveil périodique.
- Une vingtaine de messages de commit plus légers viennent compléter la liste
  par défaut, qui passe de 18 à 38 entrées.

### Modifié

- Une série de commits rattrapés n'ouvre plus qu'une seule connexion à GitHub :
  les commits sont faits localement, le push est unique.

### Corrigé

- Windows : la tâche planifiée ne tournait pas quand la machine était sur
  batterie. Windows applique par défaut `DisallowStartIfOnBatteries`, et saute
  chaque réveil sans le signaler nulle part : sur un portable débranché, aucun
  commit n'était fait de la journée. La tâche est désormais posée à partir
  d'une définition XML qui désarme ce réglage et demande le rattrapage d'un
  réveil manqué.

## [1.0.0] - 2026-09-14

Première version.

### Ajouté

- `commytho login` et `commytho logout` : jeton GitHub stocké dans le trousseau
  du système, avec repli sur un fichier restreint si aucun trousseau n'est
  disponible.
- `commytho init` : choix d'un dépôt existant ou création d'un nouveau dépôt.
- `commytho up` et `commytho down` : pose et retrait de la tâche planifiée, avec
  une implémentation par système (schtasks, launchd, systemd, cron).
- `commytho status` et `commytho plan` : état courant et programme à venir.
- `commytho run` : le réveil appelé par le planificateur.
- Programme quotidien tiré de façon déterministe, réparti dans une plage horaire,
  plafonné à vingt commits par jour par défaut.
- Publication sur PyPI depuis GitHub Actions, déclenchée par un tag.
