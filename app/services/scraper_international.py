# app/services/scraper_international.py
"""
Service de scraping international pour NOBILIS X V2
Sources : UNGM (ONU) et UNDP (PNUD)
Règle : "international" marqué dans source_country
"""

import logging
import random
import time
from datetime import datetime
from sqlalchemy.orm import Session

import requests
from bs4 import BeautifulSoup

from app.config import get_settings
from app.models.tender import Tender
# Import des constantes et helpers du scraper local pour rester cohérent
from app.services.scraper import USER_AGENTS, _guess_sector 

logger = logging.getLogger(__name__)
settings = get_settings()

class InternationalScraperService:
    """Moteur de collecte pour les appels d'offres mondiaux (UNGM/UNDP)"""

    def __init__(self, db: Session):
        self.db = db
        self.session = requests.Session()
        self.ungm_search_url = "https://www.ungm.org/Public/Notice/Search"
        self.undp_url = "https://procurement-notices.undp.org/"
        self.ungm_base = "https://www.ungm.org"

    def _apply_stealth_delay(self):
        """Délai aléatoire 3-8s (Anti-blocage V2)"""
        delay = random.uniform(3, 8)
        logger.info(f"⏳ International stealth delay: {delay:.2f}s...")
        time.sleep(delay)

    def _get_headers(self):
        """Génération Headers avec rotation UA"""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest"
        }

    def _scrape_ungm(self, limit: int = 30) -> list[dict]:
        """Scrape le portail UNGM via requête AJAX POST"""
        logger.info("📡 Scraping UNGM (Nations Unies)...")
        results = []
        
        # Filtres de recherche : On prend les 50 derniers avis actifs
        payload = {
            "PageIndex": 0,
            "PageSize": 50,
            "IsActive": True
        }

        try:
            self._apply_stealth_delay()
            response = self.session.post(
                self.ungm_search_url,
                json=payload,
                headers=self._get_headers(),
                timeout=30
            )
            
            if response.status_code in [403, 429]:
                logger.error(f"❌ Blocage UNGM ({response.status_code})")
                return []

            response.raise_for_status()
            # UNGM renvoie un fragment HTML à injecter
            soup = BeautifulSoup(response.text, "html.parser")
            rows = soup.find_all("div", class_="tableRow")

            for row in rows:
                if len(results) >= limit: break
                
                title_tag = row.find("span", class_="ungm-title")
                if not title_tag: continue
                
                # Récupération des colonnes via les attributs data-description
                org_tag = row.find("div", {"data-description": "Organization"})
                deadline_tag = row.find("div", {"data-description": "Deadline"})
                link_tag = row.find("a", href=True)
                
                title = title_tag.get_text(strip=True)
                org = org_tag.get_text(strip=True) if org_tag else "UN Agency"
                deadline_str = deadline_tag.get_text(strip=True) if deadline_tag else None
                url = self.ungm_base + link_tag["href"] if link_tag else ""

                results.append({
                    "title": f"[{org}] {title}",
                    "description": f"Appel d'offres international UNGM - Agence: {org}",
                    "source_url": url,
                    "deadline_str": deadline_str,
                    "sector": _guess_sector(title),
                })
        except Exception as e:
            logger.error(f"❌ Erreur UNGM : {e}")

        return results

    def _scrape_undp(self, limit: int = 20) -> list[dict]:
        """Scrape le portail UNDP (PNUD)"""
        logger.info("📡 Scraping UNDP (PNUD)...")
        results = []

        try:
            self._apply_stealth_delay()
            headers = self._get_headers()
            del headers["X-Requested-With"] # Pas besoin d'AJAX pour UNDP
            
            response = self.session.get(self.undp_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            # La structure est un tableau avec des liens dans la 1ère colonne
            # Basé sur l'analyse read_url_content précédente
            notices = soup.find_all("a", href=lambda x: x and "view_negotiation.cfm" in x)

            for link in notices:
                if len(results) >= limit: break
                
                # Le lien contient le titre
                title = link.get_text(strip=True)
                if not title or len(title) < 10: continue
                
                url = link["href"]
                if not url.startswith("http"):
                    url = "https://procurement-notices.undp.org/" + url.lstrip("/")

                results.append({
                    "title": f"[UNDP] {title}",
                    "description": "Appel d'offres international PNUD (UNDP)",
                    "source_url": url,
                    "deadline_str": None, # Deadline nécessite un second clic (optionnel V2)
                    "sector": _guess_sector(title),
                })
        except Exception as e:
            logger.error(f"❌ Erreur UNDP : {e}")

        return results

    def _tender_exists(self, source_url: str) -> bool:
        return self.db.query(Tender).filter(Tender.source_url == source_url).first() is not None

    def scrape_international_tenders(self, force: bool = False) -> list[Tender]:
        """Point d'entrée principal pour la veille internationale"""
        # La fenêtre temporelle est gérée par le scheduler ou via 'force'
        logger.info("🌍 Lancement collecte internationale (UNGM + UNDP)")
        
        all_data = []
        all_data.extend(self._scrape_ungm())
        all_data.extend(self._scrape_undp())

        new_tenders = []
        for td in all_data:
            if not self._tender_exists(td["source_url"]):
                tender = Tender(
                    title=td["title"][:500],
                    description=td["description"],
                    source_url=td["source_url"],
                    sector=td["sector"],
                    location="International",
                    source_country="international", # Identifiant V2
                    is_analyzed=False
                )
                
                # Parsing date si présente
                if td["deadline_str"]:
                    # Pour UNGM ex: 15-Apr-2024
                    try:
                        # Nettoyage simple pour UNGM (souvent "DD-Mon-YYYY")
                        clean_date = td["deadline_str"].split(" ")[0]
                        tender.deadline = datetime.strptime(clean_date, "%d-%b-%Y")
                    except: pass

                self.db.add(tender)
                new_tenders.append(tender)

        self.db.commit()
        logger.info(f"✅ Collecte internationale terminée : {len(new_tenders)} nouveaux visés.")
        return new_tenders
