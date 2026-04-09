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


def job_check_expirations():
    """
    L'Horloge Nobilis : Vérifie les expirations toutes les 2 heures.
    - PASS : 48h (2 jours)
    - ENTRY/ELITE : 1 an (365 jours)
    Bloque l'envoi des rapports si expiré.
    """
    logger.info("🕒 NOBILIS X — VERIFICATION DES EXPIRATIONS...")
    try:
        from app.models.enterprise import Enterprise
        from app.models.individual import Individual
        now = datetime.utcnow()

        with get_db_context() as db:
            # 1. Entreprises
            expired_ent = db.query(Enterprise).filter(
                Enterprise.subscription_expires_at < now,
                ~Enterprise.subscription_plan.like("SUSPENDED_%")
            ).all()

            for ent in expired_ent:
                old_plan = ent.subscription_plan
                ent.subscription_plan = f"SUSPENDED_{old_plan}"
                logger.warning(f"🚫 Compte Entreprise SUSPENDU (Expiré) : {ent.name} (Plan final: {ent.subscription_plan})")

            # 2. Individus
            expired_ind = db.query(Individual).filter(
                Individual.subscription_expires_at < now,
                ~Individual.subscription_plan.like("SUSPENDED_%")
            ).all()

            for ind in expired_ind:
                old_plan = ind.subscription_plan
                ind.subscription_plan = f"SUSPENDED_{old_plan}"
                logger.warning(f"🚫 Compte Particulier SUSPENDU (Expiré) : {ind.full_name} (Plan final: {ind.subscription_plan})")

            db.commit()
            if expired_ent or expired_ind:
                logger.info(f"✅ Total suspension effectuée : {len(expired_ent) + len(expired_ind)}")
            else:
                logger.info("✅ Aucun compte expiré détecté.")

    except Exception as e:
        logger.error(f"ERREUR JOB EXPIRATION: {e}", exc_info=True)


def job_daily_reminders():
    """
    Job quotidien (9h00) pour envoyer les rappels d'expiration
    - 7 jours avant
    - 3 jours avant
    """
    logger.info("=" * 60)
    logger.info(f"NOBILIS X — ENVOI DES RAPPELS D'EXPIRATION | {datetime.now().isoformat()}")
    logger.info("=" * 60)

    try:
        from app.models.enterprise import Enterprise
        from app.models.individual import Individual
        now_date = datetime.utcnow().date()

        with get_db_context() as db:
            email_service_ent = EmailService(db)
            email_service_ind = IndividualEmailService(db)

            # 1. Parcourir les Entreprises
            ents = db.query(Enterprise).filter(
                Enterprise.subscription_expires_at.isnot(None),
                ~Enterprise.subscription_plan.like("SUSPENDED_%")
            ).all()

            for ent in ents:
                if not ent.subscription_expires_at:
                    continue
                days_left = (ent.subscription_expires_at.date() - now_date).days
                if days_left in [7, 3]:
                    logger.info(f"📧 Envoi rappel ({days_left} jours) à l'entreprise {ent.name}")
                    email_service_ent.send_expiration_reminder(ent, days_left)

            # 2. Parcourir les Particuliers
            inds = db.query(Individual).filter(
                Individual.subscription_expires_at.isnot(None),
                ~Individual.subscription_plan.like("SUSPENDED_%")
            ).all()

            for ind in inds:
                if not ind.subscription_expires_at:
                    continue
                days_left = (ind.subscription_expires_at.date() - now_date).days
                if days_left in [7, 3]:
                    logger.info(f"📧 Envoi rappel ({days_left} jours) au particulier {ind.full_name}")
                    email_service_ind.send_expiration_reminder(ind, days_left)

    except Exception as e:
        logger.error(f"ERREUR JOB RAPPELS EXPIRATION: {e}", exc_info=True)


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

    # 4. HORLOGE NOBILIS : Toutes les 2 heures (pour être réactif sur l'essai de 48h)
    scheduler.add_job(
        func=job_check_expirations,
        trigger=CronTrigger(hour="*/2"),
        id="check_expirations",
        name="NOBILIS X — Horloge Expirations & Abonnements",
        replace_existing=True,
    )

    # 5. RAPPELS D'EXPIRATION : Tous les jours à 9h00
    scheduler.add_job(
        func=job_daily_reminders,
        trigger=CronTrigger(hour=9, minute=0),
        id="daily_reminders",
        name="NOBILIS X — Rappels d'expiration (7j / 3j)",
        replace_existing=True,
    )

    scheduler.start()
    return scheduler


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)