# commytho

Un outil en ligne de commande qui pousse des commits sur un dépôt qui vous
appartient, à un rythme que vous fixez, depuis votre propre machine.

Le nom vient de `commit` et de `mytho`. 

Le programme ne prétend pas faire autre
chose que ce qu'il fait : ajouter une ligne dans un fichier, la commiter, la
pousser. Personne n'est dupe, vous non plus.

C'est avant tout un prétexte pour manipuler des sujets utiles : 

planificateurs natifs des trois systèmes, stockage de secret dans un trousseau, API GitHub,
empaquetage Python, publication automatisée...

## Installation

```sh
pipx install commytho
```

`pipx` installe l'outil dans son propre environnement et met la commande sur le
PATH, sans polluer votre Python système. Si vous ne l'avez pas :

```sh
python -m pip install --user pipx
python -m pipx ensurepath
```

Il vous faut aussi `git`, et Python 3.10 ou plus récent.

## Prise en main

```sh
commytho login     # enregistre un jeton GitHub dans le trousseau du système
commytho init      # choisit le dépôt cible, ou le crée
commytho up        # pose la tâche planifiée
commytho status    # montre où en sont les choses
commytho down      # retire la tâche planifiée
```

Un exemple complet, du jeton au premier commit :

```sh
commytho login
commytho init --create journal --private
commytho up --per-day 1-3 --days lun-ven --window 09:00-19:00 --max 20
```

## Le jeton GitHub

`commytho login` demande un jeton d'accès personnel à portée fine, à créer sur
[https://github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new).

Permissions à cocher, dans `Repository permissions` :

| Permission         | Niveau         | À quoi ça sert                                       |
| ------------------ | -------------- | ------------------------------------------------------ |
| `Contents`       | Read and write | pousser les commits                                    |
| `Metadata`       | Read-only      | ajouté d'office par GitHub                            |
| `Administration` | Read and write | seulement si vous voulez que commytho crée le dépôt |

Limitez la portée au dépôt concerné et mettez une date d'expiration. Si vous
choisissez un dépôt existant, la permission `Administration` est inutile.

Le jeton part dans le trousseau du système : Gestionnaire d'identification sous
Windows, Trousseau d'accès sous macOS, Secret Service sous Linux. Il n'apparaît
ni dans la configuration, ni dans `.git/config`, ni dans la liste des processus.
Sur une machine sans trousseau, typiquement un serveur sans session graphique,
commytho se rabat sur un fichier lisible par votre seul compte et vous prévient.

Pour tout effacer : `commytho logout`.

## Les options de `commytho up`

| Option                     | Défaut         | Effet                                                         |
| -------------------------- | --------------- | ------------------------------------------------------------- |
| `--per-day N` ou `N-M` | `1-3`         | nombre de commits tirés chaque jour actif                    |
| `--days`                 | `lun-ven`     | jours actifs :`lun-ven`, `sam,dim`, `tous`, `weekend` |
| `--window`               | `09:00-19:00` | plage horaire, à l'heure locale de la machine                |
| `--max N`                | `20`          | plafond quotidien, quoi qu'il arrive                          |
| `--tick MINUTES`         | `30`          | fréquence de réveil du planificateur                        |
| `--messages FICHIER`     | liste interne   | vos propres messages de commit, un par ligne                  |
| `--dry-run`              |                 | affiche le programme prévu sans rien installer               |

`commytho plan --days 14` montre les deux prochaines semaines sans rien écrire.

## Comment ça marche

Le planificateur du système réveille commytho toutes les trente minutes par
défaut. Ce réveil ne commite pas forcément.

Chaque jour, commytho tire un programme, par exemple 09:47, 13:12 et 17:29. Le
tirage est déterministe pour un couple dépôt et date : deux réveils du même jour
retombent sur le même programme, même si le fichier d'état a disparu. Un réveil
ne fait quelque chose que si un créneau est arrivé à échéance.

Les créneaux sont répartis en tranches égales dans la plage horaire, avec un
tirage à l'intérieur de chaque tranche. On évite ainsi les paquets de commits à
la même minute tout en gardant un rythme irrégulier.

Si la machine était éteinte et que plusieurs créneaux sont en retard, commytho
n'en rattrape qu'un seul, le plus récent, et abandonne les autres. Repousser six
commits d'un coup après un week-end serait exactement le contraire du but.

Le plafond de vingt commits par jour est là pour la même raison. Vous pouvez le
relever, l'outil vous dira simplement ce qu'il en pense.

## Le planificateur, système par système

| Système           | Mécanisme                         | Vérifier à la main                      |
| ------------------ | ---------------------------------- | ----------------------------------------- |
| Windows            | tâche planifiée`commytho`      | `schtasks /Query /TN commytho`          |
| macOS              | agent launchd`com.commytho.tick` | `launchctl list \| grep commytho`        |
| Linux              | minuterie systemd utilisateur      | `systemctl --user list-timers commytho` |
| Linux sans systemd | entrée crontab marquée           | `crontab -l`                            |

Tout est posé sous votre compte utilisateur, sans droits administrateur, et
survit au redémarrage.

Sous Linux, une minuterie utilisateur s'arrête quand vous fermez votre session.
Pour qu'elle continue à tourner, activez le maintien de session :

```sh
loginctl enable-linger "$USER"
```

## Où sont les fichiers

| Rôle                            | Windows                     | macOS                                      | Linux                       |
| -------------------------------- | --------------------------- | ------------------------------------------ | --------------------------- |
| Configuration                    | `%APPDATA%\commytho`      | `~/Library/Application Support/commytho` | `~/.config/commytho`      |
| État, journal, copie du dépôt | `%LOCALAPPDATA%\commytho` | `~/Library/Application Support/commytho` | `~/.local/share/commytho` |

`commytho status` affiche les chemins exacts de votre machine. La copie locale
du dépôt appartient à commytho : vos dépôts de travail ne sont jamais touchés.

## Dépannage

**Les commits n'apparaissent pas sur mon profil.** GitHub ne compte une
contribution que si l'adresse de l'auteur appartient au compte. commytho utilise
l'adresse `noreply` du compte, ce qui remplit toujours cette condition. Vérifiez
avec `commytho status` que l'auteur est bien le vôtre.

**Le dépôt est privé.** Activez `Private contributions` dans les réglages du
graphe de contributions, sinon rien ne s'affiche.

**Rien ne se passe.** Regardez le journal, dont `commytho status` donne le
chemin. Pour forcer un commit tout de suite et voir ce qui se passe :

```sh
commytho run --force --verbose
```

**Le jeton a expiré.** `commytho login` à nouveau, le jeton est remplacé.

## Développement

```sh
git clone https://github.com/GuillaumeYves/commytho
cd commytho
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
```

Les tests ne touchent ni au réseau, ni à git, ni à la configuration réelle de la
machine : tout passe par des dossiers temporaires.

## Publication

Les versions partent sur PyPI depuis GitHub Actions, déclenchées par un tag.
Voir `CONTRIBUTING.md` pour la marche à suivre.

## Licence

MIT.
