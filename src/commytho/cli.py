"""Point d'entrée en ligne de commande.

Chaque sous-commande est une fonction cmd_xxx qui renvoie un code de sortie.
Les messages destinés à un humain passent par print, ceux destinés au fichier
de journal passent par journalise. La commande run, lancée par le
planificateur, fait les deux.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import date, datetime, timedelta

from . import __version__, auth, github, messages, paths, planner, repo, state
from . import config as conf
from .schedulers import get_scheduler
from .schedulers.base import SchedulerError


def journalise(texte: str) -> None:
    """Ajoute une ligne horodatée au journal local de commytho."""
    paths.ensure_dirs()
    horodatage = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with paths.log_file().open("a", encoding="utf-8") as fichier:
        fichier.write(f"{horodatage} {texte}\n")


def erreur(texte: str) -> int:
    print(f"Erreur : {texte}", file=sys.stderr)
    return 1


# --------------------------------------------------------------------------
# login et logout
# --------------------------------------------------------------------------


def cmd_login(args: argparse.Namespace) -> int:
    print("Connexion à GitHub")
    print()
    print("commytho a besoin d'un jeton d'accès personnel à portée fine.")
    print("Créez-le ici : https://github.com/settings/personal-access-tokens/new")
    print()
    print("Permissions nécessaires, en Repository permissions :")
    print("  - Contents : Read and write   (pour pousser les commits)")
    print("  - Metadata : Read-only        (ajouté d'office par GitHub)")
    print("  - Administration : Read and write, uniquement si vous voulez que")
    print("    commytho crée le dépôt pour vous")
    print()
    print("Limitez la portée au seul dépôt concerné, et mettez une date d'expiration.")
    print()

    token = args.token or getpass.getpass("Jeton (la saisie reste invisible) : ").strip()
    if not token:
        return erreur("Aucun jeton saisi.")

    try:
        utilisateur = github.current_user(token)
    except github.GitHubError as exc:
        return erreur(str(exc))

    mode = auth.store(token)
    if mode == "fichier":
        print()
        print("Attention : aucun trousseau système disponible sur cette machine.")
        print(f"Le jeton a été écrit dans {paths.config_dir() / 'token'}, en accès")
        print("restreint à votre compte. Préférez un trousseau si vous en installez un.")

    configuration = conf.load()
    configuration.author.name = utilisateur.get("name") or utilisateur["login"]
    configuration.author.email = github.noreply_email(utilisateur)
    conf.save(configuration)

    print()
    print(f"Connecté en tant que {utilisateur['login']}.")
    print(f"Les commits seront signés {configuration.author.name} <{configuration.author.email}>.")
    print()
    print("Étape suivante : commytho init")
    return 0


def cmd_logout(args: argparse.Namespace) -> int:
    if auth.forget():
        print("Jeton supprimé de cette machine.")
    else:
        print("Aucun jeton à supprimer.")
    return 0


# --------------------------------------------------------------------------
# init
# --------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    try:
        token = auth.retrieve()
    except auth.AuthError as exc:
        return erreur(str(exc))

    if not repo.git_available():
        return erreur("git est introuvable. Installez-le, puis relancez.")

    try:
        utilisateur = github.current_user(token)
    except github.GitHubError as exc:
        return erreur(str(exc))

    configuration = conf.load()
    if not configuration.author.email:
        configuration.author.name = utilisateur.get("name") or utilisateur["login"]
        configuration.author.email = github.noreply_email(utilisateur)

    choix_depot = args.repo
    creer = args.create

    # Sans option, on demande. Avec options, on ne demande rien, ce qui rend la
    # commande utilisable dans un script.
    if not choix_depot and not creer:
        print("Quel dépôt commytho doit-il alimenter ?")
        print("  1) un dépôt qui existe déjà")
        print("  2) un nouveau dépôt, que commytho va créer")
        reponse = input("Votre choix [1] : ").strip() or "1"
        if reponse == "2":
            saisie = input("Nom du nouveau dépôt [commytho-journal] : ").strip()
            creer = saisie or "commytho-journal"
            prive = input("Le rendre privé ? [o/N] : ").strip().lower() in {"o", "oui", "y"}
            args.private = prive
        else:
            choix_depot = input(f"Dépôt, au format {utilisateur['login']}/nom : ").strip()

    if creer:
        nom = creer
        try:
            print(f"Création de {utilisateur['login']}/{nom} sur GitHub...")
            donnees = github.create_repo(
                token,
                nom,
                private=args.private,
                description="Journal tenu par commytho",
            )
        except github.GitHubError as exc:
            return erreur(
                f"{exc}\nSi le message parle de permissions, le jeton a besoin de "
                "Administration : Read and write pour créer un dépôt."
            )
        proprietaire, _, nom_depot = donnees["full_name"].partition("/")
    else:
        if "/" not in choix_depot:
            choix_depot = f"{utilisateur['login']}/{choix_depot}"
        proprietaire, _, nom_depot = choix_depot.partition("/")
        donnees = github.get_repo(token, proprietaire, nom_depot)
        if donnees is None:
            return erreur(
                f"Dépôt {proprietaire}/{nom_depot} introuvable avec ce jeton. "
                "Vérifiez le nom, et que le jeton donne bien accès à ce dépôt."
            )
        if not donnees.get("permissions", {}).get("push", False):
            return erreur(
                f"Le jeton n'a pas le droit d'écrire dans {proprietaire}/{nom_depot}. "
                "Ajoutez la permission Contents : Read and write."
            )

    configuration.repo = conf.Repo(
        owner=proprietaire,
        name=nom_depot,
        branch=args.branch or donnees.get("default_branch") or "main",
        private=bool(donnees.get("private")),
    )
    configuration.target_file = args.file or configuration.target_file
    conf.save(configuration)

    print(f"Dépôt cible : {configuration.repo.full_name} (branche {configuration.repo.branch})")
    print("Préparation de la copie locale...")
    try:
        checkout = repo.ensure_checkout(configuration, token)
    except repo.GitError as exc:
        return erreur(str(exc))
    print(f"Copie locale prête : {checkout}")

    if configuration.repo.private:
        print()
        print("Ce dépôt est privé. Pour que les commits apparaissent sur votre profil,")
        print("activez Private contributions dans les réglages du graphe GitHub.")

    print()
    print("Étape suivante : commytho up")
    return 0


# --------------------------------------------------------------------------
# up et down
# --------------------------------------------------------------------------


def cmd_up(args: argparse.Namespace) -> int:
    configuration = conf.load()
    if not configuration.is_linked:
        return erreur("Aucun dépôt configuré. Lancez d'abord : commytho init")
    if not auth.has_token():
        return erreur("Aucun jeton enregistré. Lancez d'abord : commytho login")

    planning = configuration.schedule
    try:
        if args.days:
            planning.days = conf.parse_days(args.days)
        if args.per_day:
            planning.min_per_day, planning.max_per_day = conf.parse_range(args.per_day)
        if args.window:
            planning.window_start, planning.window_end = conf.parse_window(args.window)
        if args.max is not None:
            planning.cap_per_day = args.max
        if args.tick is not None:
            planning.tick_minutes = max(1, args.tick)
        if args.rattrapage is not None:
            planning.catch_up = max(0, args.rattrapage)
    except conf.ConfigError as exc:
        return erreur(str(exc))

    if planning.max_per_day > planning.cap_per_day:
        print(
            f"Note : le maximum demandé ({planning.max_per_day}) dépasse le plafond "
            f"({planning.cap_per_day}). Le plafond gagne."
        )
    if planning.cap_per_day > conf.RECOMMENDED_MAX_PER_DAY:
        print(
            f"Attention : un plafond de {planning.cap_per_day} commits par jour se voit. "
            f"Au-delà de {conf.RECOMMENDED_MAX_PER_DAY}, le rythme n'a plus rien d'humain."
        )

    if args.messages:
        try:
            pool = messages.load_pool(args.messages)
        except OSError as exc:
            return erreur(f"Fichier de messages illisible : {exc}")
        print(f"{len(pool)} messages personnalisés chargés.")

    print(f"Rythme retenu : {planning.describe()}")
    print(f"Réveil du planificateur toutes les {planning.tick_minutes} minutes.")
    print()
    _affiche_apercu(configuration, jours=7)

    if args.dry_run:
        print()
        print("Essai à blanc : rien n'a été installé.")
        return 0

    try:
        scheduler = get_scheduler()
        identifiant = scheduler.install(planning.tick_minutes)
    except SchedulerError as exc:
        return erreur(str(exc))

    configuration.installed = conf.Installed(
        kind=scheduler.kind,
        identifier=identifiant,
        installed_at=datetime.now().isoformat(timespec="seconds"),
    )
    conf.save(configuration)
    journalise(f"up : {scheduler.kind} {identifiant}, {planning.describe()}")

    print()
    print(f"commytho est en route ({scheduler.kind} : {identifiant}).")
    print("Pour tout arrêter : commytho down")
    return 0


def cmd_down(args: argparse.Namespace) -> int:
    configuration = conf.load()
    try:
        scheduler = get_scheduler()
        retire = scheduler.uninstall()
    except SchedulerError as exc:
        return erreur(str(exc))

    configuration.installed = conf.Installed()
    conf.save(configuration)
    journalise("down : tâche planifiée retirée")

    if retire:
        print("Tâche planifiée retirée. Plus aucun commit automatique.")
    else:
        print("Aucune tâche planifiée n'était posée.")
    print("La configuration et le jeton sont conservés. Pour le jeton : commytho logout")
    return 0


# --------------------------------------------------------------------------
# status et plan
# --------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> int:
    configuration = conf.load()
    etat = state.load()

    print(f"commytho {__version__}")
    print()
    print(f"Jeton         : {'enregistré' if auth.has_token() else 'absent'}")
    if configuration.is_linked:
        print(
            f"Dépôt         : {configuration.repo.full_name} "
            f"(branche {configuration.repo.branch}"
            f"{', privé' if configuration.repo.private else ''})"
        )
        print(f"Fichier suivi : {configuration.target_file}")
    else:
        print("Dépôt         : non configuré")
    if configuration.author.email:
        print(f"Auteur        : {configuration.author.name} <{configuration.author.email}>")
    print(f"Rythme        : {configuration.schedule.describe()}")

    try:
        scheduler = get_scheduler()
        pose = scheduler.status()
    except SchedulerError as exc:
        pose = f"indisponible ({exc})"
    print(f"Planificateur : {pose or 'aucune tâche posée'}")

    print()
    aujourdhui = date.today()
    if configuration.is_linked:
        programme = planner.plan_for_day(
            configuration.schedule, aujourdhui, configuration.repo.full_name
        )
        faits = etat.done if etat.day == aujourdhui.isoformat() else []
        restants = [c for c in programme if c not in faits]
        print(f"Aujourd'hui   : {len(faits)} commit(s) faits sur {len(programme)} prévus")
        if programme:
            print(f"  programme   : {', '.join(programme)}")
        if restants:
            print(f"  à venir     : {', '.join(restants)}")
    print(f"Total cumulé  : {etat.total_commits} commit(s)")
    print()
    print(f"Configuration : {paths.config_file()}")
    print(f"Journal       : {paths.log_file()}")
    return 0


def _affiche_apercu(configuration: conf.Config, jours: int) -> None:
    """Montre le programme des prochains jours, sans rien écrire."""
    print(f"Aperçu des {jours} prochains jours :")
    for decalage in range(jours):
        jour = date.today() + timedelta(days=decalage)
        programme = planner.plan_for_day(configuration.schedule, jour, configuration.repo.full_name)
        etiquette = f"  {conf.DAY_NAMES[jour.weekday()]} {jour.isoformat()}"
        if programme:
            print(f"{etiquette} : {len(programme)} commit(s) à {', '.join(programme)}")
        else:
            print(f"{etiquette} : repos")


def cmd_plan(args: argparse.Namespace) -> int:
    configuration = conf.load()
    if not configuration.is_linked:
        return erreur("Aucun dépôt configuré. Lancez d'abord : commytho init")
    _affiche_apercu(configuration, jours=args.days)
    return 0


# --------------------------------------------------------------------------
# run : le réveil appelé par le planificateur
# --------------------------------------------------------------------------


def cmd_run(args: argparse.Namespace) -> int:
    configuration = conf.load()
    if not configuration.is_linked:
        journalise("run : aucun dépôt configuré, rien à faire")
        return erreur("Aucun dépôt configuré. Lancez d'abord : commytho init")

    try:
        token = auth.retrieve()
    except auth.AuthError as exc:
        journalise(f"run : {exc}")
        return erreur(str(exc))

    aujourdhui = date.today()
    maintenant = datetime.now().strftime("%H:%M")
    programme = planner.plan_for_day(
        configuration.schedule, aujourdhui, configuration.repo.full_name
    )

    etat = state.roll_over(state.load(), aujourdhui, programme)

    # Avec --force, on commite tout de suite, ce qui sert à vérifier une
    # installation sans attendre le prochain créneau.
    creneaux = [maintenant] if args.force else planner.due_slots(programme, etat.done, maintenant)

    if not creneaux:
        state.save(etat)
        if args.verbose:
            print("Rien à faire pour le moment.")
        return 0

    restant = configuration.schedule.cap_per_day - len(etat.done)
    if restant <= 0:
        journalise(f"run : plafond du jour atteint ({configuration.schedule.cap_per_day})")
        state.save(etat)
        return 0

    # Politique de rattrapage. Par défaut on ne commite que le créneau le plus
    # récent et on abandonne les autres : rejouer six commits d'un coup après un
    # week-end machine éteinte serait le contraire du but recherché. Avec
    # --rattrapage 0, tout le programme manqué est rejoué, ce qui convient quand
    # la machine n'est allumée qu'une partie de la journée.
    rattrapage = configuration.schedule.catch_up
    limite = len(creneaux) if rattrapage <= 0 else rattrapage
    limite = max(1, min(limite, restant))

    abandonnes = creneaux[:-limite]
    retenus = creneaux[-limite:]
    if abandonnes:
        etat.done.extend(abandonnes)
        journalise(f"run : créneaux passés abandonnés ({', '.join(abandonnes)})")

    pool = messages.load_pool(args.messages)
    a_commiter = [(creneau, messages.pick(pool, aujourdhui, creneau)) for creneau in retenus]

    try:
        empreintes = repo.make_commits(configuration, token, aujourdhui, a_commiter)
    except repo.GitError as exc:
        journalise(f"run : échec du commit ({exc})")
        return erreur(str(exc))

    if not args.force:
        etat.done.extend(retenus)
    etat.total_commits += len(empreintes)
    etat.last_run = datetime.now().isoformat(timespec="seconds")
    state.save(etat)

    if len(empreintes) == 1:
        resume = f"commit {empreintes[0]} pour le créneau {retenus[0]} ({a_commiter[0][1]})"
    else:
        resume = f"{len(empreintes)} commits rattrapés, de {retenus[0]} à {retenus[-1]}"
    journalise(f"run : {resume}")
    if args.verbose or args.force:
        print(f"{resume.capitalize()}, poussé vers {configuration.repo.full_name}")
    return 0


# --------------------------------------------------------------------------
# Analyse des arguments
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="commytho",
        description="Des commits planifiés, bridés, et lancés depuis votre machine.",
    )
    parser.add_argument("--version", action="version", version=f"commytho {__version__}")
    sous = parser.add_subparsers(dest="command", metavar="commande")

    p_login = sous.add_parser("login", help="enregistrer un jeton GitHub")
    p_login.add_argument(
        "--token",
        help="jeton passé directement, pour un script. Préférez la saisie interactive.",
    )
    p_login.set_defaults(func=cmd_login)

    p_logout = sous.add_parser("logout", help="oublier le jeton enregistré")
    p_logout.set_defaults(func=cmd_logout)

    p_init = sous.add_parser("init", help="choisir ou créer le dépôt cible")
    p_init.add_argument("--repo", help="dépôt existant, au format proprietaire/nom")
    p_init.add_argument("--create", metavar="NOM", help="créer un nouveau dépôt de ce nom")
    p_init.add_argument("--private", action="store_true", help="créer le dépôt en privé")
    p_init.add_argument("--branch", help="branche visée, par défaut celle du dépôt")
    p_init.add_argument("--file", help="fichier alimenté dans le dépôt, par défaut journal.md")
    p_init.set_defaults(func=cmd_init)

    p_up = sous.add_parser("up", help="poser la tâche planifiée")
    p_up.add_argument("--per-day", metavar="N|N-M", help="commits par jour, par exemple 1-4")
    p_up.add_argument("--days", metavar="JOURS", help="jours actifs, par exemple lun-ven")
    p_up.add_argument(
        "--window", metavar="HH:MM-HH:MM", help="plage horaire, par exemple 09:00-19:00"
    )
    p_up.add_argument("--max", type=int, metavar="N", help="plafond quotidien, 20 par défaut")
    p_up.add_argument("--tick", type=int, metavar="MINUTES", help="intervalle de réveil")
    p_up.add_argument(
        "--rattrapage",
        type=int,
        metavar="N",
        help="créneaux en retard rejoués par réveil (0 pour tous)",
    )
    p_up.add_argument("--messages", metavar="FICHIER", help="liste de messages, un par ligne")
    p_up.add_argument("--dry-run", action="store_true", help="afficher sans rien installer")
    p_up.set_defaults(func=cmd_up)

    p_down = sous.add_parser("down", help="retirer la tâche planifiée")
    p_down.set_defaults(func=cmd_down)

    p_status = sous.add_parser("status", help="afficher l'état courant")
    p_status.set_defaults(func=cmd_status)

    p_plan = sous.add_parser("plan", help="afficher le programme à venir")
    p_plan.add_argument("--days", type=int, default=7, help="nombre de jours affichés")
    p_plan.set_defaults(func=cmd_plan)

    p_run = sous.add_parser("run", help="exécuter un réveil, normalement appelé par le système")
    p_run.add_argument("--force", action="store_true", help="commiter maintenant, hors programme")
    p_run.add_argument("--verbose", action="store_true", help="afficher ce qui se passe")
    p_run.add_argument("--messages", metavar="FICHIER", help="liste de messages, un par ligne")
    p_run.set_defaults(func=cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except conf.ConfigError as exc:
        return erreur(str(exc))
    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    sys.exit(main())
