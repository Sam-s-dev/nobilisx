# scripts/test_weekly_cycle_individuals.py
import sys
import os
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal
from app.services.email_service_individual import IndividualEmailService

def test():
    print("🚀 Démarrage manuel du cycle d'envoi pour tous les particuliers...")
    db = SessionLocal()
    try:
        service = IndividualEmailService(db)
        results = service.send_all_individual_reports()
        print(f"📊 Résultats de l'envoi en masse : {results}")
    except Exception as e:
        print(f"❌ Erreur : {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test()
