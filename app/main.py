# app/main.py
"""
NOBILIS X V2 — Système Expert de Veille & Analyse des Appels d'Offres.
L'intelligence des marchés. La noblesse de l'avance.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers import enterprises, tenders, analyses, individuals, auth, admin
from app.scheduler.jobs import init_scheduler, shutdown_scheduler
from app.limiter import limiter

# Configuration du logging
import os
log_handlers = [logging.StreamHandler()]
try:
    os.makedirs("logs", exist_ok=True)
    log_handlers.append(logging.FileHandler("logs/tender_analyzer.log", mode="a", encoding="utf-8"))
except Exception:
    pass  # Pas de fichier log si le dossier n'est pas accessible

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=log_handlers,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# === Configuration Sentry (Connecteur de Surveillance) ===
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration()],
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )
    logger.info("✅ Connecteur Sentry active")

# === Configuration Rate Limiter ===
# Le limiteur est importé depuis app.limiter pour éviter les imports circulaires
app_limiter = limiter


# === Lifespan : startup + shutdown ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application"""
    # --- STARTUP ---
    logger.info(" Démarrage de NOBILIS X")
    logger.info(f"   Version: {settings.APP_VERSION}")
    logger.info(f"   Debug: {settings.DEBUG}")

    # Initialiser la base de données
    init_db()
    logger.info("✅ Base de données initialisée")

    # Valider la configuration SMTP/Mailjet
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD or not settings.SMTP_FROM:
        logger.warning("⚠️" * 30)
        logger.warning("⚠️ CONFIGURATION SMTP INCOMPLÈTE : Les e-mails ne pourront pas s'envoyer !")
        logger.warning(f"  SMTP_HOST: {settings.SMTP_HOST}")
        logger.warning(f"  SMTP_USER: {'Définie' if settings.SMTP_USER else 'VIDE (Avertissement)'}")
        logger.warning(f"  SMTP_PASSWORD: {'Définie' if settings.SMTP_PASSWORD else 'VIDE (Avertissement)'}")
        logger.warning(f"  SMTP_FROM: {'Définie' if settings.SMTP_FROM else 'VIDE (Avertissement)'}")
        logger.warning("  -> Pour corriger sur Render, configurez les variables d'environnement :")
        logger.warning("     SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM dans l'onglet Environment.")
        logger.warning("⚠️" * 30)
    else:
        logger.info(f"📧 SMTP configuré avec succès (Hôte : {settings.SMTP_HOST}, Expéditeur : {settings.SMTP_FROM})")

    # Démarrer le scheduler
    init_scheduler()
    logger.info("✅ Scheduler initialisé")

    logger.info("🟢 Application prête")

    yield  # L'application tourne ici

    # --- SHUTDOWN ---
    logger.info("🔴 Arrêt de l'application...")
    shutdown_scheduler()
    logger.info("👋 Application arrêtée proprement")


# === Création de l'application FastAPI ===
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## 🏆 NOBILIS X — Système Expert de Veille & Analyse

L'intelligence des marchés. La noblesse de l'avance.
Fait en Guinée. Conçu pour que les meilleurs gagnent.

### Fonctionnalités :
- **Surveillance centralisée** des sources officielles (JAO, TELEMO, UNGM, UNDP)
- **Analyse instantanée de documents** (50+ pages) via IA
- **Indice de Crédibilité (0-100)** pour cibler les marchés gagnables
- **Filtrage de précision** sur 20 secteurs spécialisés
- **Rapport personnalisé chaque lundi à 7h** directement en boîte mail

### Endpoints principaux :
- `POST /enterprises` — Enregistrer une entreprise
- `POST /individuals` — Inscrire un particulier
- `GET /tenders` — Lister les appels d'offres
- `GET /analysis/{enterprise_id}` — Analyses avec Indice de Crédibilité
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# === Middleware CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montage du limiteur
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# === Montage des fichiers statiques ===
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# === Gestion globale des erreurs ===
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handler global pour les erreurs non gérées"""
    logger.error(f"❌ Erreur non gérée: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Erreur interne du serveur",
            "error": str(exc) if settings.DEBUG else "Contactez l'administrateur",
        },
    )


# === Enregistrement des routers ===
app.include_router(enterprises.router, prefix="/api/v1")
app.include_router(tenders.router, prefix="/api/v1")
app.include_router(analyses.router, prefix="/api/v1")
app.include_router(individuals.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


# === Endpoints utilitaires ===
@app.get("/", tags=["Root"])
def root():
    """Page d'accueil - Sert le frontend"""
    import os
    index_path = os.path.join("app", "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Health check pour Docker et monitoring"""
    from app.database import engine

    try:
        # Vérifier la connexion DB
        with engine.connect() as conn:
            conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "database": db_status,
        "version": settings.APP_VERSION,
    }


@app.get("/scheduler/status", tags=["Scheduler"])
def scheduler_status():
    """Vérifie le statut du scheduler"""
    from app.scheduler.jobs import scheduler

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
        })

    return {
        "running": scheduler.running,
        "jobs": jobs,
    }