# app/database.py
"""
Configuration SQLAlchemy et gestion des sessions PostgreSQL
"""

import time
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Log de l'URL utilisée
db_url = settings.database_url
logger.info(f"🔌 URL de connexion DB résolue (voir logs config pour détails)")

# Ajouter sslmode=require pour Supabase si pas déjà présent
if "supabase" in db_url and "sslmode" not in db_url:
    separator = "&" if "?" in db_url else "?"
    db_url = f"{db_url}{separator}sslmode=require"
    logger.info(" SSL activé pour Supabase")

# Création du moteur avec pool de connexions
engine = create_engine(
    db_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,       # Vérifie la connexion avant utilisation
    pool_recycle=1800,         # Recycle les connexions après 30min
    connect_args={
        "connect_timeout": 10,  # Timeout de connexion 10s
    },
    echo=settings.DEBUG,       # Log SQL en mode debug
)

# Factory de sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base déclarative pour tous les modèles
Base = declarative_base()


def get_db():
    """
    Dépendance FastAPI : fournit une session DB par requête.
    La session est automatiquement fermée après la requête.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Context manager pour utilisation hors FastAPI (scheduler, scripts).
    Usage:
        with get_db_context() as db:
            db.query(...)
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """
    Crée toutes les tables en base avec retry.
    À appeler au démarrage de l'application.
    """
    # Import tous les modèles pour que SQLAlchemy les enregistre
    from app.models import enterprise, tender, analysis, email_log  # noqa: F401

    max_retries = 5
    retry_delay = 3  # secondes

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"🔌 Tentative de connexion DB ({attempt}/{max_retries})...")
            # Test de connexion d'abord
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ Connexion DB réussie")
            
            # Créer les tables
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Tables créées/vérifiées avec succès")
            return
        except Exception as e:
            logger.error(f"❌ Tentative {attempt}/{max_retries} échouée: {e}")
            if attempt < max_retries:
                logger.info(f"⏳ Retry dans {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Backoff exponentiel
            else:
                logger.critical(f"💀 Impossible de se connecter à la DB après {max_retries} tentatives")
                raise