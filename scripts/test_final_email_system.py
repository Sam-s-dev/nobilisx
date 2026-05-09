# scripts/test_final_email_system.py
import sys
import os
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app.models.enterprise import Enterprise
from app.services.email_service import EmailService

def test():
    db = SessionLocal()
    try:
        # 1. On cherche ou on crée une entreprise de test avec l'email vérifié
        email_ok = "generalouki21@gmail.com"
        enterprise = db.query(Enterprise).filter(Enterprise.email == email_ok).first()
        
        if not enterprise:
            print(f"🏗️ Création d'une entreprise de test pour {email_ok}...")
            enterprise = Enterprise(
                name="Test Final V2",
                email=email_ok,
                sector="Technologie",
                subscription_plan="ELITE"
            )
            db.add(enterprise)
            db.commit()
            db.refresh(enterprise)

        # 2. On lance l'envoi via le service officiel du projet
        print(f"🚀 Envoi de l'email de bienvenue via EmailService...")
        service = EmailService(db)
        success = service.send_welcome_email(enterprise)
        
        if success:
            print("✅ SUCCÈS TOTAL : L'email de bienvenue a été envoyé via le service système !")
        else:
            print("❌ ÉCHEC : Le service n'a pas pu envoyer l'email.")
            
    except Exception as e:
        print(f"❌ ERREUR SYSTÈME : {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test()
