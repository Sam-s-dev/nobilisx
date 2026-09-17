# scripts/test_smtp_direct.py
"""
Test de l'envoi SMTP classique uniquement (sans passer par les API HTTP).

Utile pour vérifier que le SMTP fonctionne en local. Ne sert à rien sur Render :
les hébergeurs cloud bloquent les ports SMTP sortants.

Pour tester TOUS les fournisseurs : python scripts/test_email.py <destinataire>
"""

import os
import sys

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv

load_dotenv()

from app.config import get_settings  # noqa: E402
from app.services.email_sender import _send_smtp  # noqa: E402


def test_direct():
    settings = get_settings()
    recipient = settings.EMAIL_FROM or settings.SMTP_FROM

    print("Test direct de l'envoi SMTP...")
    print(f"  Expéditeur   : {recipient}")
    print(f"  Destinataire : {recipient}")
    print(f"  Serveur SMTP : {settings.SMTP_HOST}:{settings.SMTP_PORT}")

    try:
        _send_smtp(
            to_email=recipient,
            subject="Nobilis X V2 - Test Direct SMTP",
            html_body=(
                "<html><body>"
                "<h2 style='color:#1e3a8a;'>Test SMTP</h2>"
                "<p>Ce message valide l'envoi SMTP de <b>NOBILIS X</b>.</p>"
                "</body></html>"
            ),
            text_body="Test SMTP NOBILIS X.",
        )
        print("SUCCÈS : l'email a été envoyé via SMTP.")
    except Exception as e:
        print(f"ÉCHEC : {e}")


if __name__ == "__main__":
    test_direct()
