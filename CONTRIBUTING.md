# Contribuer

## Monter l'environnement

```sh
python -m venv .venv
. .venv/bin/activate        # sous Windows : .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

## Avant de proposer un changement

```sh
python -m pytest
python -m ruff check .
python -m ruff format .
```

La CI lance la même chose sur Windows, macOS et Linux, de Python 3.10 à 3.13.
Elle construit aussi le paquet et vérifie que la commande installée répond, ce
qu'un test unitaire ne prouve pas.

## Règles de code

- Les identifiants restent en anglais, la documentation et les commentaires sont
  en français.
- Un commentaire explique pourquoi, pas quoi. Si le quoi n'est pas lisible, le
  code est à revoir avant le commentaire.
- Aucune dépendance supplémentaire sans raison sérieuse. `keyring` est la seule,
  parce qu'écrire soi-même l'accès aux trousseaux des trois systèmes serait pire.
- Les tests ne touchent ni au réseau, ni à git, ni à la vraie configuration de la
  machine.

## Publier une version

Le dépôt utilise le Trusted Publishing de PyPI : GitHub Actions prouve son
identité par OIDC, aucun jeton d'API ne traîne dans les secrets.

### Une fois pour toutes

1. Créer le projet sur PyPI, ou réserver le nom.
2. Dans `Publishing`, ajouter un éditeur de confiance GitHub :
   - Owner : `GuillaumeYves`
   - Repository : `commytho`
   - Workflow : `release.yml`
   - Environment : `pypi`
3. Dans les réglages GitHub du dépôt, créer l'environnement `pypi`. Vous pouvez
   y exiger une approbation manuelle avant chaque publication.

### À chaque version

1. Mettre à jour `__version__` dans `src/commytho/__init__.py`.
2. Compléter `CHANGELOG.md` : déplacer les entrées de `Non publié` vers la
   nouvelle version, avec sa date.
3. Commiter, puis poser le tag :

```sh
git commit -am "Version 0.2.0"
git tag v0.2.0
git push origin main --tags
```

Le workflow `release.yml` vérifie d'abord que le tag correspond à
`__version__`, rejoue les tests sur les trois systèmes, construit les archives,
publie sur PyPI, puis crée la release GitHub avec les archives attachées.

Un tag qui ne correspond pas à la version échoue avant toute publication. C'est
volontaire : PyPI refuse le réenvoi d'un numéro déjà pris, une erreur à ce
niveau coûte un numéro de version.
