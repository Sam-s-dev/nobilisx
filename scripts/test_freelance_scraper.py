# scripts/test_freelance_scraper.py
import sys
import os
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal
from app.services.scraper_freelance import FreelanceScraperService
from app.services.ai_analyzer import AIAnalyzerService

def run_scrape():
    print("🚀 Démarrage forcé de la collecte Freelance...")
    db = SessionLocal()
    try:
        scraper = FreelanceScraperService(db)
        new_missions = scraper.scrape_freelance_missions()
        print(f"✅ Collecte terminée ! Nombre de nouvelles missions : {len(new_missions)}")
        
        if new_missions:
            print("🧠 Lancement de l'analyse IA (Groq) pour les nouvelles missions freelance...")
            analyzer = AIAnalyzerService(db)
            analyses = analyzer.analyze_all_pending()
            print(f"✅ Analyse IA terminée ! {len(analyses)} nouvelles analyses générées.")
        else:
            print("ℹ️ Aucune nouvelle mission à analyser.")
            
    except Exception as e:
        print(f"❌ Erreur : {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_scrape()
