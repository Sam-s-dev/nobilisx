# app/services/scraper.py
"""
Service de scraping discret - Telemo, JAO Guinée et autres sources (V2)
Gère le téléchargement des pages, rotation des User-Agents, délais aléatoires.
"""

import os
import logging
import hashlib
import time
import random
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.tender import Tender

logger = logging.getLogger(__name__)
settings = get_settings()

DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

# 10 User-Agents réels pour la rotation anti-blocage (V2)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.2; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
]

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
    "Connection": "keep-alive",
}

def _guess_sector(text: str) -> str:
    """Helper global pour deviner le secteur à partir d'un titre."""
    text_lower = text.lower()
    sector_map = {
        "agri": "Agriculture, Pêche & Développement Rural",
        "educ": "Éducation & Formation",
        "ener": "Energie, Eau & Environnement",
        "info": "Informatique & Télécommunications",
        "sante": "Santé & Paramédical",
        "travaux": "Travaux Publics & Construction",
    }
    for kw, sector in sector_map.items():
        if kw in text_lower: return sector
    return "Services Généraux & Prestations diverses"


class ScraperService:
    """Service de scraping des appels d'offres refactorisé pour la V2 (Anti-blocage)"""

    def __init__(self, db: Session):
        self.db = db
        self.telemo_url = settings.TELEMO_BASE_URL
        self.jao_url = settings.JAO_BASE_URL
        self.session = requests.Session()

    def _get_random_headers(self):
        """Génère des headers avec un User-Agent aléatoire."""
        headers = DEFAULT_HEADERS.copy()
        headers["User-Agent"] = random.choice(USER_AGENTS)
        return headers

    def _apply_stealth_delay(self):
        """Injecte un délai aléatoire entre 3 et 8 secondes (V2 Politeness)."""
        delay = random.uniform(3, 8)
        logger.info(f"⏳ Stealth delay: {delay:.2f}s...")
        time.sleep(delay)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    )
    def _fetch_page(self, url: str, timeout: int = 30) -> str:
        """Récupère HTML avec rotation UA et délai aléatoire."""
        self._apply_stealth_delay()
        headers = self._get_random_headers()
        
        try:
            logger.info(f"📡 Fetching: {url}")
            response = self.session.get(url, headers=headers, timeout=timeout)
            
            if response.status_code == 429:
                logger.warning(f"⚠️ Rate limited (429) on {url}. Waiting longer...")
                time.sleep(30) # Délai supplémentaire en cas de 429
                response.raise_for_status()
            
            response.raise_for_status()
            return response.text
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [403, 429]:
                logger.error(f"❌ Blocage détecté ({e.response.status_code}) sur {url}")
                return "" # On continue sans crash
            raise e

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=2, min=5),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    )
    def _download_pdf(self, url: str, timeout: int = 60) -> str | None:
        """Télécharge PDF avec rotation UA et délai aléatoire."""
        self._apply_stealth_delay()
        headers = self._get_random_headers()
        
        try:
            logger.info(f"📥 Downloading PDF: {url}")
            response = self.session.get(url, headers=headers, timeout=timeout, stream=True)
            
            if response.status_code in [403, 429]:
                logger.error(f"❌ Blocage PDF ({response.status_code}) : {url}")
                return None

            response.raise_for_status()

            filename = hashlib.md5(url.encode()).hexdigest() + ".pdf"
            filepath = DOWNLOADS_DIR / filename

            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            return str(filepath)
        except Exception as e:
            logger.error(f"❌ Échec téléchargement PDF {url}: {e}")
            return None

    # --- Parsers existants ---

    def _parse_telemo_listings(self, html: str) -> list[dict]:
        if not html: return []
        soup = BeautifulSoup(html, "html.parser")
        tenders = []
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    year_text = ""
                    entity_text = ""
                    link_href = None
                    for cell in cells:
                        text = cell.get_text(strip=True)
                        link = cell.find("a")
                        if link and link.get("href"):
                            href = link["href"]
                            if not href.startswith("javascript:"):
                                link_href = href if href.startswith("http") else f"{self.telemo_url}{href}"
                        if text and text.isdigit() and len(text) == 4: year_text = text
                        elif text and len(text) > 5: entity_text = text
                    if entity_text:
                        title = f"Plan de passation des marchés {year_text} — {entity_text}"
                        source_url = link_href or f"https://www.google.com/search?q=plan+passation+marche+{year_text}+{entity_text}+Guinee"
                        tenders.append({
                            "title": title[:500],
                            "description": f"Plan de passation des marchés publics {year_text} de {entity_text}",
                            "source_url": source_url,
                            "deadline_str": None,
                            "location": "Guinée",
                            "sector": _guess_sector(entity_text),
                        })
        return tenders

    def _parse_jao_listings(self, html: str, category: str = None) -> list[dict]:
        if not html: return []
        soup = BeautifulSoup(html, "html.parser")
        tenders = []
        articles = soup.find_all(["article", "div"], class_=lambda c: c and ("post" in str(c).lower() or "entry" in str(c).lower()))
        if not articles:
            articles = soup.find_all("h2", class_=lambda c: c and "entry-title" in str(c).lower())
            if not articles: articles = soup.find_all(["h1", "h2", "h3"])

        for article in articles:
            link = article.find("a")
            if not link or not link.get("href"): continue
            title = link.get_text(strip=True)
            if not title or len(title) < 10: continue
            if any(kw in title.lower() for kw in ["recrutement", "avis d'attribution", "résultats"]): continue
            tenders.append({
                "title": title[:500],
                "description": f"Appel d'offres publié sur JAO Guinée : {title}",
                "source_url": link["href"],
                "deadline_str": None,
                "location": "Guinée",
                "sector": category or _guess_sector(title),
            })
        return tenders

    def _tender_exists(self, source_url: str) -> bool:
        return self.db.query(Tender).filter(Tender.source_url == source_url).first() is not None

    def _is_scraping_window(self) -> bool:
        """Vérifie si on est dans la fenêtre autorisée (Samedi 22h - Dimanche 02h)."""
        now = datetime.now()
        # weekday(): 5 = samedi, 6 = dimanche
        # Samedi de 22h a 23h59
        if now.weekday() == 5 and now.hour >= 22:
            return True
        # Dimanche de 00h a 02h
        if now.weekday() == 6 and now.hour < 2:
            return True
        return False

    def scrape_tenders(self, force: bool = False) -> list[Tender]:
        """Exécute le scraping (JAO + Telemo)."""
        if not force and not self._is_scraping_window():
            logger.info("🚫 Hors fenêtre de scraping (Samedi 22h-02h). Scraping annulé.")
            return []

        logger.info(f"🚀 Démarrage du scraping V2 (force={force})")
        all_tender_data = []

        # 1. JAO (Toutes catégories fondamentales)
        jao_categories = {
            "BTP": f"{self.jao_url}/category/appels-d-offres/travaux-publics-construction/",
            "Santé": f"{self.jao_url}/category/appels-d-offres/sante-medicaments/",
            "IT": f"{self.jao_url}/category/appels-d-offres/informatique-telecommunications/",
            "Services": f"{self.jao_url}/category/appels-d-offres/services-generaux-prestations-diverses/",
        }
        for cat, url in jao_categories.items():
            try:
                html = self._fetch_page(url)
                all_tender_data.extend(self._parse_jao_listings(html, category=cat))
            except Exception as e: logger.warning(f"Sortie JAO {cat} en erreur: {e}")

        # 2. Telemo
        try:
            telemo_p = f"{self.telemo_url}/eb/bpp/selectPageProcurementPlan.do?menuId=EB03010100&leftTopFlag=t"
            html = self._fetch_page(telemo_p)
            all_tender_data.extend(self._parse_telemo_listings(html))
        except Exception as e: logger.warning(f"Telemo error: {e}")

        # Stockage
        new_tenders = []
        for td in all_tender_data:
            if not self._tender_exists(td["source_url"]):
                tender = Tender(
                    title=td["title"],
                    description=td.get("description"),
                    source_url=td["source_url"],
                    sector=td.get("sector"),
                    location=td.get("location", "Guinée"),
                    is_analyzed=False,
                )
                self.db.add(tender)
                self.db.flush() # Pour avoir l'ID
                logger.info(f"➕ Debug: Tender added with ID {tender.id}")
                new_tenders.append(tender)
        
        self.db.commit()
        logger.info(f"✅ Scraping terminé : {len(new_tenders)} nouveaux trouvés.")
        return new_tenders