# app/models/__init__.py
"""
Modèles SQLAlchemy - Import centralisé
"""
from app.models.enterprise import Enterprise
from app.models.tender import Tender
from app.models.analysis import Analysis
from app.models.email_log import EmailLog
from app.models.subscription import Subscription
from app.models.individual import Individual

__all__ = ["Enterprise", "Tender", "Analysis", "EmailLog", "Subscription", "Individual"]