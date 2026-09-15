# Journal des versions

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et les
numéros suivent [SemVer](https://semver.org/lang/fr/).

## [Non publié]

### Corrigé

- Le workflow passait une fois par jour, à l'heure ronde. C'est le créneau que
  GitHub documente comme le plus retardé, celui que tout le monde demande, et
  une exécution planifiée peut y être sautée sans un mot. Il y a désormais deux
  passages, à une minute tirée du nom du dépôt, jamais la minute zéro. Un
  passage sauté ne laisse plus de trou : le suivant reprend ce qui manque, et
  une visite qui n'a rien à faire ne coûte que quelques secondes de runner.

## [1.2.0] - 2026-09-15

### Ajouté

- `commytho github` dépose dans le dépôt cible un workflow qui tient le journal
  depuis GitHub, une visite par jour, après la fermeture de la plage horaire.
  Une machine éteinte ne fait donc plus de trou. Le workflow reprend le rythme
  de la configuration locale, ne demande aucun secret, et se contente de la
  permission `contents: write`. `--remove` le retire, `--dry-run` l'affiche,
  `--tz` donne le fuseau dans lequel dater les commits.
- `commytho ci` est la visite elle-même, prévue pour tourner dans un runner.
  Elle ne lit ni configuration, ni fichier d'état, ni trousseau : tout vient de
  ses options et de la copie du dépôt déjà présente. Sa date de départ borne la
  reprise : le journal du dépôt étant sa seule mémoire, sans elle la première
  visite prendrait la semaine précédente pour une semaine manquée.

### Modifié

- Un créneau déjà consigné dans le journal n'est plus recommité. Le journal
  versé dans le dépôt devient la mémoire partagée de tous les commytho qui
  visent ce dépôt : la machine et le workflow peuvent tourner ensemble sans se
  marcher dessus, et un fichier d'état perdu ne fait plus de doublons.
- `make_commits` rend la liste des commits réellement posés, créneau compris,
  plutôt que des empreintes seules. Les comptes rendus disent donc ce qui a
  été fait plutôt que ce qui avait été demandé.
- Les messages de commit par défaut sont ponctués. L'ordre et la longueur de la
  liste n'ont pas bougé : un créneau retombe sur le même message qu'avant, avec
  son point.
- La publication est rejouable. Un tag redéplacé refaisait échouer le workflow
  sur un numéro déjà pris ; l'envoi ignore désormais ce qui est déjà en ligne,
  et la release GitHub est mise à jour plutôt que recréée.

## [1.1.0] - 2026-09-15

### Ajouté

- Le fichier suivi laisse la place au suivant passé mille lignes : `journal.md`,
  puis `journal-2.md`, et ainsi de suite. Le seuil se règle avec
  `commytho up --max-lines N`, et `0` désactive la rotation. Le numéro en cours
  est déduit des fichiers présents dans le dépôt, sans rien stocker à côté :
  effacer l'état local ne fait pas repartir la rotation en arrière.
- `commytho up --rattrapage-jours N` : nombre de journées passées reprises à la
  réouverture de session. Une machine restée éteinte plusieurs jours solde son
  arriéré au premier réveil, chaque commit gardant la date et l'heure de son
  créneau d'origine. La valeur par défaut reste `0`, soit le jour courant seul.
- L'état garde une trace des créneaux honorés les jours précédents, élaguée à
  la durée de reprise demandée. Sans elle, une reprise ne saurait pas
  distinguer une journée déjà soldée d'une journée entièrement manquée.

### Modifié

- Windows : plus aucune fenêtre n'apparaît pendant les commits. La tâche est
  marquée masquée, et les processus git sont lancés sans console. Jusqu'ici,
  pythonw.exe évitait bien la fenêtre du planificateur, mais chaque appel à
  git, qui est une application console, en faisait ouvrir une par Windows : une
  fenêtre noire clignotait au premier plan et volait le focus, plusieurs fois
  par commit.
- `commytho up` marque comme honorés les créneaux du jour déjà écoulés.
  Changer de rythme ne déclenche donc plus une salve rétroactive : le nouveau
  programme commence à l'heure de la pose, et les journées suivantes sont
  complètes.
- `commytho status` affiche le fichier réellement alimenté et le seuil de
  rotation, plutôt que le seul nom de base.

### Corrigé

- Un programme serré rendait moins de commits que le nombre tiré. Avec
  quarante commits dans une heure, les tranches font moins d'une minute et
  plusieurs tirages tombaient sur la même : les doublons disparaissaient en
  silence. Chaque doublon est désormais décalé sur la minute libre la plus
  proche, sans sortir de la plage horaire.

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
