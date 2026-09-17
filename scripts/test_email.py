# scripts/test_email.py
"""
Diagnostic d'envoi d'email — teste chaque fournisseur configuré, un par un.

Usage :
    python scripts/test_email.py destinataire@exemple.com
    python scripts/test_email.py destinataire@exemple.com --provider brevo

À lancer aussi bien en local que sur Render (Shell) : c'est le même code que
celui utilisé en production, donc le résultat est représentatif.
"""

import argparse
import os
import sys

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv

load_dotenv()

from app.services.email_sender import (  # noqa: E402
    PROVIDERS,
    configured_providers,
    describe_config,
    provider_order,
    send_email,
)

HTML = """<h1 style="color:#c9a84c;">NOBILIS X — Test</h1>
<p>Si vous lisez ce message, ce fournisseur fonctionne.</p>
<p>Fournisseur testé : <strong>{provider}</strong></p>"""

TEXT = "NOBILIS X - Test d'envoi. Fournisseur : {provider}"


def show_config() -> dict:
    config = describe_config()
    print("=" * 62)
    print("CONFIGURATION EMAIL")
    print("=" * 62)
    print(f"  Expéditeur        : {config['from_email'] or '(aucun)'}")
    print(f"  Domaine public    : {'oui (Gmail & co)' if config['from_is_public_domain'] else 'non'}")
    print(f"  Ordre d'essai     : {' -> '.join(config['order'])}")
    print(f"  Configurés        : {', '.join(config['available']) or '(aucun)'}")
    print(f"  Fournisseur actif : {config['active_provider'] or '(aucun)'}")
    print()
    print("  Clés détectées :")
    for name, present in config["keys"].items():
        print(f"    {'[OK]' if present else '[--]'} {name}")

    if config["warnings"]:
        print()
        print("  AVERTISSEMENTS :")
        for warning in config["warnings"]:
            print(f"    ! {warning}")
    print()
    return config


def test_provider(name: str, recipient: str) -> bool:
    """Teste un fournisseur isolément, en court-circuitant la cascade."""
    print(f"--- {name} ---")
    try:
        message_id = PROVIDERS[name](
            recipient,
            f"NOBILIS X - Test {name}",
            HTML.format(provider=name),
            TEXT.format(provider=name),
            None,
        )
        print(f"    OK  envoyé à {recipient} | id={message_id}\n")
        return True
    except Exception as e:
        print(f"    KO  {e}\n")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Teste l'envoi d'email NOBILIS X")
    parser.add_argument("recipient", nargs="?", help="adresse de destination")
    parser.add_argument("--provider", choices=sorted(PROVIDERS), help="ne tester que celui-ci")
    parser.add_argument("--config-only", action="store_true", help="afficher la config sans envoyer")
    args = parser.parse_args()

    config = show_config()

    if args.config_only:
        return 0

    if not args.recipient:
        parser.error("indiquez une adresse de destination (ou utilisez --config-only)")

    if args.provider:
        targets = [args.provider]
    else:
        targets = configured_providers() or list(provider_order())

    print("=" * 62)
    print(f"TEST D'ENVOI vers {args.recipient}")
    print("=" * 62)

    results = {name: test_provider(name, args.recipient) for name in targets}

    print("=" * 62)
    working = [name for name, ok in results.items() if ok]
    if working:
        print(f"Fournisseurs fonctionnels : {', '.join(working)}")
        print(f"En production, la cascade utilisera : {working[0]}")
    else:
        print("Aucun fournisseur n'a fonctionné.")
        print("Piste la plus rapide : créer un compte Brevo (300 mails/jour gratuits,")
        print("aucun nom de domaine requis), valider l'expéditeur, puis renseigner")
        print("BREVO_API_KEY dans les variables d'environnement.")
    print("=" * 62)

    # Vérification finale de la cascade complète (ce que fait réellement l'app)
    if working and not args.provider:
        print("\nTest de la cascade complète (send_email) ...")
        try:
            result = send_email(
                args.recipient,
                "NOBILIS X - Test cascade",
                HTML.format(provider="cascade"),
                TEXT.format(provider="cascade"),
            )
            print(f"    OK  via {result['provider']} | id={result['message_id']}")
        except Exception as e:
            print(f"    KO  {e}")

    return 0 if working else 1


if __name__ == "__main__":
    sys.exit(main())
