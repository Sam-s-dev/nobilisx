import os
import sys
from datetime import datetime, timedelta

# Ajouter le répertoire parent au path pour importer app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db_context
from app.models.enterprise import Enterprise
from app.services.email_service import EmailService

def main():
    print("Test: Rappels d'expiration et Validation d'Abonnement")
    print("=" * 60)
    
    with get_db_context() as db:
        # 1. Créer une entreprise fictive qui expire dans 7 jours
        now = datetime.utcnow()
        expire_in_7_days = now + timedelta(days=7)
        
        # Test Email
        test_email = "trillionnx@gmail.com"
        
        # S'assurer que le compte n'existe pas déjà
        existing = db.query(Enterprise).filter(Enterprise.email == test_email).first()
        if existing:
            db.delete(existing)
            db.commit()
            
        test_ent = Enterprise(
            name="Test Extension Nobilis",
            sector="Technologie",
            email=test_email,
            subscription_plan="ELITE",
            subscription_expires_at=expire_in_7_days
        )
        db.add(test_ent)
        db.commit()
        db.refresh(test_ent)
        
        print(f"[OK] Compte {test_ent.name} cree.")
        print(f"[DATE] Date d'expiration definie au: {test_ent.subscription_expires_at.date()} (Dans 7 jours)")
        
        # 2. Simuler le job_daily_reminders pour ce compte
        days_left = (test_ent.subscription_expires_at.date() - now.date()).days
        if days_left == 7:
            print(f"[EMAIL] Condition '7 jours restants' remplie. Envoi de l'e-mail de rappel...")
            email_service = EmailService(db)
            # Normalement le service catch les exceptions ou renvoie True/False
            success = email_service.send_expiration_reminder(test_ent, days_left)
            if success:
                print("[OK] E-mail de rappel envoye avec succes !")
            else:
                print("[ERROR] Echec de l'envoi de l'e-mail de rappel (Veuillez verifier .env et la configuration Mailjet).")
        
        # 3. Simuler la route Admin /validate (Paiement avant l'expiration)
        print("\n[SIMULATION] Le client paie avant l'expiration de son abonnement...")
        duration = timedelta(days=365)
        
        old_expire = test_ent.subscription_expires_at
        
        if test_ent.subscription_expires_at and test_ent.subscription_expires_at > now:
            test_ent.subscription_expires_at += duration
            print(".. Logique ajoutant 365 jours a la date actuelle d'expiration appliquee.")
        else:
            test_ent.subscription_expires_at = now + duration
            print(".. Logique de reinitialisation a partir d'aujourd'hui + 365 jours.")
            
        db.commit()
        db.refresh(test_ent)
        
        print(f"[DATE] Ancienne expiration: {old_expire.date()}")
        print(f"[DATE] NOUVELLE expiration: {test_ent.subscription_expires_at.date()}")
        print("[OK] Le compte est continuellement actif jusqu'a sa nouvelle date de fin.")
        
        # Nettoyage
        print("\n[CLEAN] Nettoyage de l'utilisateur de test...")
        db.delete(test_ent)
        db.commit()
        print("[OK] Nettoyage termine.")

if __name__ == "__main__":
    main()
