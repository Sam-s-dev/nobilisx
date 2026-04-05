# app/scheduler/jobs.py
"""
Scheduler APScheduler - NOBILIS X V2
- Samedi 22h30 : Collecte des appels d'offres (Scraping discret)
- Lundi 7h : Analyse IA + Scoring + Envoi des rapports hebdomadaires (Bi-segment)
- Toutes les 2h (8h-20h) : Alertes temps réel pour ELITE (Entreprises)
"""

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

from app.config import get_settings
from app.database import get_db_context
from app.services.scraper import ScraperService
from app.services.scraper_international import InternationalScraperService
from app.services.scraper_freelance import FreelanceScraperService
from app.services.pdf_parser import PDFParserService
from app.services.ai_analyzer import AIAnalyzerService
from app.services.email_service import EmailService
from app.services.email_service_individual import IndividualEmailService

logger = logging.getLogger(__name__)
settings = get_settings()

scheduler = BackgroundScheduler()

def job_weekly_scrape():
    """
    Job planifié chaque SAMEDI à 22h30 : Collecte massive de toutes les sources.
    Respecte l'anti-blocage (délais aléatoires entre requêtes).
    """
    logger.info("=" * 60)
    logger.info(f"NOBILIS X — COLLECTE BI-SEGMENT | {datetime.now().isoformat()}")
    logger.info("=" * 60)

    try:
        with get_db_context() as db:
            # 1. Collecte Locale (JAO, TELEMO)
            logger.info("--- Phase 1/3 : Scraping Local ---")
            scraper = ScraperService(db)
            new_tenders = scraper.scrape_tenders() 
            
            # 2. Collecte Internationale (UNGM, UNDP)
            logger.info("--- Phase 2/3 : Scraping International ---")
            scraper_intl = InternationalScraperService(db)
            new_intl = scraper_intl.scrape_international_tenders()

            # 3. Collecte Freelance (Upwork, Freelancer)
            logger.info("--- Phase 3/3 : Scraping Freelance ---")
            scraper_fl = FreelanceScraperService(db)
            new_fl = scraper_fl.scrape_freelance_missions()
            
            logger.info(f"Collecte terminee : {len(new_tenders)} locaux, {len(new_intl)} intl et {len(new_fl)} freelance ajoutes.")

    except Exception as e:
        logger.error(f"ERREUR SCRAPING HEBDOMADAIRE: {e}", exc_info=True)


def job_weekly_cycle():
    """
    Job planifié chaque LUNDI à 7h : Analyse IA + Scoring + Envois aux deux segments.
    """
    logger.info("=" * 60)
    logger.info(f"NOBILIS X — CYCLE COMPLET (LUNDI) | {datetime.now().isoformat()}")
    logger.info("=" * 60)

    try:
        with get_db_context() as db:
            # Étape 1 : Analyse IA de tous les nouveaux éléments
            logger.info("Étape 1/3 : Analyse IA (Groq) de tous les nouveaux elements...")
            analyzer = AIAnalyzerService(db)
            analyses = analyzer.analyze_all_pending()
            logger.info(f"{len(analyses)} nouvelles analyses générées.")

            # Étape 2 : Rapports Entreprises
            logger.info("Étape 2/3 : Rapports hebdomadaires ENTREPRISES...")
            email_service = EmailService(db)
            res_ent = email_service.send_all_daily_reports()
            logger.info(f"Resultats Entreprises : {res_ent}")

            # Étape 3 : Rapports Particuliers
            logger.info("Étape 3/3 : Rapports hebdomadaires PARTICULIERS...")
            indiv_email_service = IndividualEmailService(db)
            res_indiv = indiv_email_service.send_all_individual_reports()
            logger.info(f"Resultats Particuliers : {res_indiv}")

    except Exception as e:
        logger.error(f"ERREUR CYCLE LUNDI: {e}", exc_info=True)


def job_elite_realtime_alert():
    """
    Job ELITE temps réel — Toutes les 2h (Entreprises uniquement).
    """
    logger.info("=" * 60)
    logger.info(f"NOBILIS X — ALERTE ELITE TEMPS RÉEL | {datetime.now().isoformat()}")
    logger.info("=" * 60)

    try:
        with get_db_context() as db:
            from app.models.enterprise import Enterprise
            from app.services.scorer import ScorerService

            # Scraping forcé mais discret
            scraper = ScraperService(db)
            new_tenders = scraper.scrape_tenders(force=True)
            
            if not new_tenders:
                logger.info("ELITE RT: Aucun nouveau tender détecté.")
                return

            # Analyse IA immédiate
            analyzer = AIAnalyzerService(db)
            analyzer.analyze_all_pending()

            # Ciblage ELITE
            elite_clients = db.query(Enterprise).filter(Enterprise.subscription_plan == "ELITE").all()
            if not elite_clients: return

            scorer = ScorerService(db)
            email_service = EmailService(db)
            for client in elite_clients:
                scored = scorer.score_all_for_enterprise(client)
                top = [s for s in scored if s["score"] >= 70]
                if top:
                    email_service.send_daily_report(client, top[:5])

    except Exception as e:
        logger.error(f"ERREUR ALERTE ELITE: {e}", exc_info=True)


def scheduler_event_listener(event):
    if event.exception:
        logger.error(f"Job {event.job_id} a échoué: {event.exception}")
    else:
        logger.info(f"Job {event.job_id} exécuté avec succès")


def init_scheduler():
    """Initialise le planning V2 Bi-segment"""
    scheduler.add_listener(scheduler_event_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    # 1. COLLECTE : Chaque Samedi à l'heure définie (Défaut 7h)
    scheduler.add_job(
        func=job_weekly_scrape,
        trigger=CronTrigger(day_of_week='sat', hour=settings.SCRAPE_SCHEDULE_HOUR, minute=0),
        id="weekly_scrape",
        name="NOBILIS X — Collecte Hebdomadaire (Samedi)",
        replace_existing=True,
    )

    # 2. ANALYSE & ENVOI : Chaque Lundi à l'heure définie (Défaut 8h)
    scheduler.add_job(
        func=job_weekly_cycle,
        trigger=CronTrigger(day_of_week='mon', hour=settings.EMAIL_SCHEDULE_HOUR, minute=0),
        id="weekly_analysis_send",
        name="NOBILIS X — Cycle Complet (Lundi)",
        replace_existing=True,
    )

    # 3. ALERTES ELITE : 2 fois par jour (Matin 8h45 & Soir 18h45)
    scheduler.add_job(
        func=job_elite_realtime_alert,
        trigger=CronTrigger(hour="8,18", minute=45),
        id="elite_realtime",
        name="NOBILIS X — Alertes ELITE",
        replace_existing=True,
    )

    scheduler.start()
    return scheduler


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)