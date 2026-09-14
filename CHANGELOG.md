# Journal des versions

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et les
numéros suivent [SemVer](https://semver.org/lang/fr/).

## [Non publié]

## [0.1.0] - 2026-09-14

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
