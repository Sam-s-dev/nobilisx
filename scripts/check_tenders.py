# scripts/check_tenders.py
import sys
import os
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app.models.tender import Tender
from app.models.individual import Individual
from app.models.analysis import Analysis

def check():
    db = SessionLocal()
    try:
        tenders_count = db.query(Tender).count()
        freelance_count = db.query(Tender).filter(Tender.source_country == "freelance").count()
        analyzed_count = db.query(Tender).filter(Tender.is_analyzed == True).count()
        analyzed_freelance = db.query(Tender).filter(Tender.source_country == "freelance", Tender.is_analyzed == True).count()
        
        print(f"📊 Nombre total d'appels d'offres (tenders) en base : {tenders_count}")
        print(f"💼 Dont freelance : {freelance_count}")
        print(f"🧠 Analysés par l'IA (is_analyzed = True) : {analyzed_count}")
        print(f"✨ Freelance analysés par l'IA : {analyzed_freelance}")
        
        # Afficher les 5 premiers tenders pour comprendre
        first_5 = db.query(Tender).limit(5).all()
        for idx, t in enumerate(first_5, 1):
            print(f"  {idx}. [{t.source_country}] Title: {t.title[:60]} | Analysé: {t.is_analyzed}")
            
    except Exception as e:
        print(f"❌ Erreur : {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check()
