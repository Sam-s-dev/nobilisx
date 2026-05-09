# scripts/test_email.py
import sys
import os
sys.path.append(os.getcwd())

from app.services.email_service import EmailService
from app.config import get_settings

def test():
    print("📧 Envoi d'un email de test via Mailjet...")
    settings = get_settings()
    recipient = settings.SMTP_FROM  # On s'envoie le mail à soi-même pour tester
    subject = "Nobilis X V2 - Test de Connexion"
    body = "Félicitations ! Votre configuration Mailjet pour Nobilis X V2 est opérationnelle."
    
    try:
        success = EmailService.send_email(recipient, subject, body)
        if success:
            print(f"✅ Email envoyé avec succès à {recipient} !")
        else:
            print("❌ Échec de l'envoi de l'email.")
    except Exception as e:
        print(f"❌ Erreur : {e}")

if __name__ == "__main__":
    test()
