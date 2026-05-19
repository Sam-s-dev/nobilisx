# scripts/test_welcome_individual.py
import sys
import os
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal
from app.models.individual import Individual
from app.services.email_service_individual import IndividualEmailService

def test_welcome():
    print("🚀 Test de l'email de bienvenue pour Particulier...")
    db = SessionLocal()
    try:
        # On récupère le particulier inscrit
        ind = db.query(Individual).filter(Individual.email == "generalouki21@gmail.com").first()
        if not ind:
            print("👤 Aucun particulier trouvé pour generalouki21@gmail.com, on en crée un temporaire pour le test.")
            ind = Individual(
                full_name="Jean Dupont",
                email="generalouki21@gmail.com",
                whatsapp="+224627271397",
                country="Guinée",
                domain="Développement Web",
                skills="Python, FastAPI, Docker",
                subscription_plan="PASS"
            )
            db.add(ind)
            db.commit()
            db.refresh(ind)
            
        print(f"👤 Particulier cible : {ind.full_name} ({ind.email})")
        service = IndividualEmailService(db)
        
        success = service.send_welcome_email(ind)
        if success:
            print("✅ SUCCÈS : L'email de bienvenue pour particulier a été envoyé avec succès !")
        else:
            print("❌ ÉCHEC : L'envoi a échoué.")
    except Exception as e:
        print(f"❌ ERREUR : {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_welcome()
