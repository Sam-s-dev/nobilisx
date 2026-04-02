# app/services/scraper_freelance.py
"""
Service de scraping Freelance pour NOBILIS X V2
Sources : Upwork (RSS) et Freelancer.com (HTML)
Cible : Segment Individual (Particuliers)
"""

import logging
import random
import time
import re
from datetime import datetime
from sqlalchemy.orm import Session

import requests
from bs4 import BeautifulSoup

from app.config import get_settings
from app.models.tender import Tender
from app.services.scraper import USER_AGENTS, _guess_sector

logger = logging.getLogger(__name__)
settings = get_settings()

class FreelanceScraperService:
    """Moteur de collecte pour les missions Freelance (Individuels)"""

    def __init__(self, db: Session):
        self.db = db
        self.session = requests.Session()
        # Upwork RSS est plus stable que le scraping direct
        self.upwork_rss_url = "https://www.upwork.com/ab/feed/jobs/rss"
        self.freelancer_url = "https://www.freelancer.com/jobs/"

    def _apply_stealth_delay(self):
        """Délai furtif 3-8s"""
        delay = random.uniform(3, 8)
        logger.info(f"⏳ Freelance stealth delay: {delay:.2f}s...")
        time.sleep(delay)

    def _get_headers(self):
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    def _scrape_upwork(self, keywords=["python", "web", "consultant", "ai"]) -> list[dict]:
        """Scrape Upwork via flux RSS par mots-clés"""
        logger.info(f"📡 Scraping Upwork (via RSS) pour les mots-clés: {keywords}")
        results = []
        
        for kw in keywords:
            try:
                self._apply_stealth_delay()
                params = {"q": kw, "sort": "recency"}
                response = self.session.get(self.upwork_rss_url, params=params, headers=self._get_headers(), timeout=30)
                
                if response.status_code != 200:
                    logger.warning(f"⚠️ Upwork RSS bloqué ou indisponible pour '{kw}' ({response.status_code})")
                    continue

                soup = BeautifulSoup(response.text, "xml") # RSS est en XML
                items = soup.find_all("item")

                for item in items:
                    title = item.title.get_text(strip=True) if item.title else "Mission Upwork"
                    link = item.link.get_text(strip=True) if item.link else ""
                    desc_html = item.description.get_text(strip=True) if item.description else ""
                    
                    # Nettoyage sommaire du HTML dans la description RSS
                    soup_desc = BeautifulSoup(desc_html, "html.parser")
                    description = soup_desc.get_text(strip=True)[:500]

                    results.append({
                        "title": f"[Upwork] {title}",
                        "description": description,
                        "source_url": link,
                        "sector": _guess_sector(title),
                    })
            except Exception as e:
                logger.error(f"❌ Erreur Upwork RSS ({kw}): {e}")

        return results

    def _scrape_freelancer(self, limit: int = 30) -> list[dict]:
        """Scrape Freelancer.com (Parsing HTML public)"""
        logger.info("📡 Scraping Freelancer.com...")
        results = []

        try:
            self._apply_stealth_delay()
            response = self.session.get(self.freelancer_url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            # Les projets sont dans des liens avec /projects/
            projects = soup.find_all("a", class_="JobSearchCard-primary-heading-link")
            
            if not projects:
                # Fallback sur une recherche de liens générique si la classe change
                projects = soup.find_all("a", href=re.compile(r"/projects/"))

            for p in projects:
                if len(results) >= limit: break
                
                title = p.get_text(strip=True)
                if not title: continue
                
                url = p["href"]
                if not url.startswith("http"):
                    url = "https://www.freelancer.com" + url

                # On cherche la description dans le parent ou le voisin
                card = p.find_parent("div", class_="JobSearchCard-primary")
                description = ""
                if card:
                    desc_tag = card.find("p", class_="JobSearchCard-Description")
                    description = desc_tag.get_text(strip=True) if desc_tag else ""

                results.append({
                    "title": f"[Freelancer] {title}",
                    "description": description[:500] or "Mission Freelancer.com",
                    "source_url": url,
                    "sector": _guess_sector(title),
                })
        except Exception as e:
            logger.error(f"❌ Erreur Freelancer.com : {e}")

        return results

    def _tender_exists(self, source_url: str) -> bool:
        return self.db.query(Tender).filter(Tender.source_url == source_url).first() is not None

    def scrape_freelance_missions(self) -> list[Tender]:
        """Point d'entrée pour la collecte Freelance"""
        logger.info("💼 Lancement collecte Freelance (Upwork + Freelancer)")
        
        all_data = []
        all_data.extend(self._scrape_upwork())
        all_data.extend(self._scrape_freelancer())

        new_missions = []
        for miss in all_data:
            if miss["source_url"] and not self._tender_exists(miss["source_url"]):
                mission = Tender(
                    title=miss["title"][:500],
                    description=miss["description"],
                    source_url=miss["source_url"],
                    sector=miss["sector"],
                    location="Remote / Remote",
                    source_country="freelance", # Identifiant V2 pour missions individuelles
                    is_analyzed=False
                )
                
                self.db.add(mission)
                new_missions.append(mission)

        self.db.commit()
        logger.info(f"✅ Collecte Freelance terminée : {len(new_missions)} nouvelles missions.")
        return new_missions
