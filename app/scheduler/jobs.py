# app/scheduler/jobs.py
"""
Scheduler APScheduler - NOBILIS X V2
- Samedi (SCRAPE_SCHEDULE_HOUR) : collecte des appels d'offres et missions
- Lundi (EMAIL_SCHEDULE_HOUR)    : analyse IA + rapports PASS et ENTRY
- Tous les jours 7h              : rapport quotidien ELITE, si nouveautes
- 8h45 et 18h45                  : alertes ELITE temps reel (score >= 70)
- Toutes les 2h                  : suspension des abonnements expires + avis
- Tous les jours 9h              : rappels d'expiration (J-7 et J-3)

Difference commerciale ENTRY / ELITE :
    ENTRY -> veille hebdomadaire
    ELITE -> veille quotidienne + alertes immediates
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

            # Étape 2 : Rapports Entreprises (PASS et ENTRY uniquement —
            # les ELITE ont déjà reçu leur rapport quotidien à 7h)
            logger.info("Étape 2/3 : Rapports hebdomadaires ENTREPRISES (hors ELITE)...")
            email_service = EmailService(db)
            res_ent = email_service.send_all_daily_reports(elite_only=False)
            logger.info(f"Resultats Entreprises : {res_ent}")

            # Étape 3 : Rapports Particuliers (idem, hors ELITE)
            logger.info("Étape 3/3 : Rapports hebdomadaires PARTICULIERS (hors ELITE)...")
            indiv_email_service = IndividualEmailService(db)
            res_indiv = indiv_email_service.send_all_individual_reports(elite_only=False)
            logger.info(f"Resultats Particuliers : {res_indiv}")

    except Exception as e:
        logger.error(f"ERREUR CYCLE LUNDI: {e}", exc_info=True)


def job_daily_elite_reports():
    """
    Rapport QUOTIDIEN des abonnés ELITE (7h) — entreprises et particuliers.

    C'est ce qui distingue ELITE d'ENTRY : veille quotidienne contre veille
    hebdomadaire. Le rapport n'est envoyé qu'aux abonnés dont le classement
    contient au moins une opportunité parue dans les dernières 24h, pour ne
    jamais réexpédier le même top 10 deux matins de suite.
    """
    logger.info("=" * 60)
    logger.info(f"NOBILIS X — RAPPORT QUOTIDIEN ELITE | {datetime.now().isoformat()}")
    logger.info("=" * 60)

    try:
        with get_db_context() as db:
            # Analyser d'abord ce que la veille temps réel a collecté cette nuit
            analyzer = AIAnalyzerService(db)
            analyzer.analyze_all_pending()

            res_ent = EmailService(db).send_all_daily_reports(elite_only=True, only_if_new=True)
            logger.info(f"ELITE quotidien — Entreprises : {res_ent}")

            res_ind = IndividualEmailService(db).send_all_individual_reports(
                elite_only=True, only_if_new=True
            )
            logger.info(f"ELITE quotidien — Particuliers : {res_ind}")

    except Exception as e:
        logger.error(f"ERREUR RAPPORT QUOTIDIEN ELITE: {e}", exc_info=True)


def job_elite_realtime_alert():
    """
    Alerte ELITE temps réel — 8h45 et 18h45, entreprises ET particuliers.

    Ne part que sur les opportunités à fort score (>= 70) et uniquement si la
    collecte forcée a trouvé du nouveau. Utilise un template dédié, distinct du
    rapport périodique, pour que l'abonné voie ce que son plan lui apporte.
    """
    logger.info("=" * 60)
    logger.info(f"NOBILIS X — ALERTE ELITE TEMPS RÉEL | {datetime.now().isoformat()}")
    logger.info("=" * 60)

    ALERT_THRESHOLD = 70

    try:
        with get_db_context() as db:
            from app.models.enterprise import Enterprise
            from app.models.individual import Individual
            from app.services.scorer import ScorerService
            from app.services.scorer_individual import IndividualScorerService
            from app.services.subscription import is_active

            # Collecte forcée mais discrète
            new_tenders = ScraperService(db).scrape_tenders(force=True)
            if not new_tenders:
                logger.info("ELITE RT : aucune nouvelle opportunité détectée.")
                return

            # Analyse IA immédiate des nouveautés
            AIAnalyzerService(db).analyze_all_pending()

            new_ids = {t.id for t in new_tenders if getattr(t, "id", None)}
            sent = 0

            # ── Entreprises ELITE ──
            scorer = ScorerService(db)
            email_service = EmailService(db)
            for client in db.query(Enterprise).filter(Enterprise.subscription_plan == "ELITE").all():
                if not is_active(client):
                    continue
                scored = scorer.score_all_for_enterprise(client)
                # Uniquement les nouveautés de ce passage, au-dessus du seuil
                top = [
                    s for s in scored
                    if s["score"] >= ALERT_THRESHOLD and (not new_ids or s["tender_id"] in new_ids)
                ]
                if top and email_service.send_elite_alert(client, top[:5]):
                    sent += 1

            # ── Particuliers ELITE ──
            indiv_scorer = IndividualScorerService(db)
            indiv_service = IndividualEmailService(db)
            for client in db.query(Individual).filter(Individual.subscription_plan == "ELITE").all():
                if not is_active(client):
                    continue
                scored = indiv_scorer.score_all_for_individual(client)
                top = [
                    s for s in scored
                    if s["score"] >= ALERT_THRESHOLD and (not new_ids or s["tender_id"] in new_ids)
                ]
                if top and indiv_service.send_elite_alert(client, top[:5]):
                    sent += 1

            logger.info(f"ELITE RT : {sent} alerte(s) envoyée(s).")

    except Exception as e:
        logger.error(f"ERREUR ALERTE ELITE: {e}", exc_info=True)


def job_check_expirations():
    """
    L'Horloge Nobilis : vérifie les expirations toutes les 2 heures.
    - PASS : 7 jours d'essai (voir app/services/subscription.PASS_TRIAL_DAYS)
    - ENTRY/ELITE : 1 an (365 jours)

    Suspend les comptes expirés ET prévient le client par email. Sans cet envoi,
    l'abonné voyait ses rapports s'arrêter sans explication ni moyen de réagir.
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
                ent.subscription_plan = f"SUSPENDED_{ent.subscription_plan}"
                logger.warning(f"🚫 Compte Entreprise SUSPENDU (Expiré) : {ent.name} (Plan final: {ent.subscription_plan})")

            # 2. Individus
            expired_ind = db.query(Individual).filter(
                Individual.subscription_expires_at < now,
                ~Individual.subscription_plan.like("SUSPENDED_%")
            ).all()

            for ind in expired_ind:
                ind.subscription_plan = f"SUSPENDED_{ind.subscription_plan}"
                logger.warning(f"🚫 Compte Particulier SUSPENDU (Expiré) : {ind.full_name} (Plan final: {ind.subscription_plan})")

            db.commit()

            # 3. Prévenir les clients concernés (après commit : le plan suspendu
            #    doit être en base pour que l'email affiche le bon message).
            if expired_ent:
                email_service = EmailService(db)
                for ent in expired_ent:
                    try:
                        email_service.send_expiration_notice(ent)
                    except Exception as e:
                        logger.error(f"Avis d'expiration non envoyé à {ent.email} : {e}")

            if expired_ind:
                indiv_service = IndividualEmailService(db)
                for ind in expired_ind:
                    try:
                        indiv_service.send_expiration_notice(ind)
                    except Exception as e:
                        logger.error(f"Avis d'expiration non envoyé à {ind.email} : {e}")

            if expired_ent or expired_ind:
                logger.info(
                    f"✅ Suspensions : {len(expired_ent) + len(expired_ind)} compte(s), "
                    "avis d'expiration envoyés."
                )
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
        misfire_grace_time=3600,
    )

    # 2. ANALYSE & ENVOI : Chaque Lundi à l'heure définie (Défaut 8h)
    scheduler.add_job(
        func=job_weekly_cycle,
        trigger=CronTrigger(day_of_week='mon', hour=settings.EMAIL_SCHEDULE_HOUR, minute=0),
        id="weekly_analysis_send",
        name="NOBILIS X — Cycle Complet (Lundi)",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # 3. RAPPORT QUOTIDIEN ELITE : tous les matins à 7h (si nouveautés)
    scheduler.add_job(
        func=job_daily_elite_reports,
        trigger=CronTrigger(hour=7, minute=0),
        id="daily_elite_reports",
        name="NOBILIS X — Rapport Quotidien ELITE",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # 4. ALERTES ELITE : 2 fois par jour (Matin 8h45 & Soir 18h45)
    scheduler.add_job(
        func=job_elite_realtime_alert,
        trigger=CronTrigger(hour="8,18", minute=45),
        id="elite_realtime",
        name="NOBILIS X — Alertes ELITE",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # 5. HORLOGE NOBILIS : toutes les 2 heures (réactivité sur la fin d'essai)
    scheduler.add_job(
        func=job_check_expirations,
        trigger=CronTrigger(hour="*/2"),
        id="check_expirations",
        name="NOBILIS X — Horloge Expirations & Abonnements",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # 6. RAPPELS D'EXPIRATION : Tous les jours à 9h00
    scheduler.add_job(
        func=job_daily_reminders,
        trigger=CronTrigger(hour=9, minute=0),
        id="daily_reminders",
        name="NOBILIS X — Rappels d'expiration (7j / 3j)",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.start()
    return scheduler


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)