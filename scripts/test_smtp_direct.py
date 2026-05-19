# scripts/test_smtp_direct.py
import sys
import os
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv()

from app.services.email_service import EmailService
from app.config import get_settings

def test_direct():
    print("🚀 Test direct de l'envoi d'email...")
    settings = get_settings()
    
    # On instancie EmailService avec db=None (car on n'utilise pas la DB pour envoyer un email direct)
    service = EmailService(db=None)
    
    recipient = settings.SMTP_FROM
    subject = "Nobilis X V2 - Test Direct SMTP"
    body = """<html><body>
    <h2 style='color: #1e3a8a;'>Test du Système Universel d'Envoi d'Emails</h2>
    <p>Ce message valide le nouveau routeur d'email SMTP/Mailjet de <b>NOBILIS X</b>.</p>
    </body></html>"""
    
    print(f"📧 Expéditeur: {settings.SMTP_FROM}")
    print(f"📧 Destinataire: {recipient}")
    print(f"🔌 SMTP Host: {settings.SMTP_HOST}:{settings.SMTP_PORT}")
    
    try:
        # On appelle le routeur d'envoi d'email directement
        success = service._send_mailjet_http(
            to_email=recipient,
            subject=subject,
            html_body=body
        )
        if success:
            print("✅ SUCCÈS : L'email a bien été routé et envoyé avec succès !")
        else:
            print("❌ ÉCHEC : Le service n'a pas pu envoyer l'email.")
    except Exception as e:
        print(f"❌ ERREUR DIRECTE : {e}")

if __name__ == "__main__":
    test_direct()
