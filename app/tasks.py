# app/tasks.py
"""
Background tasks for sending emails asynchronously to prevent blocking FastAPI request threads.
"""

import logging
from app.database import get_db_context

logger = logging.getLogger(__name__)


def send_welcome_email_task(user_id: int, user_type: str):
    """
    Background task to send a welcome/confirmation email using a fresh DB session.
    """
    logger.info(f"📧 [Background task] Starting welcome email for {user_type} ID: {user_id}")
    
    if user_type == "enterprise":
        from app.models.enterprise import Enterprise
        from app.services.email_service import EmailService
        
        with get_db_context() as db:
            user = db.query(Enterprise).filter(Enterprise.id == user_id).first()
            if not user:
                logger.error(f"❌ [Background task] Enterprise with ID {user_id} not found.")
                return
            
            try:
                service = EmailService(db)
                success = service.send_welcome_email(user)
                if success:
                    logger.info(f"✅ [Background task] Welcome email sent successfully to enterprise: {user.email}")
                else:
                    logger.warning(f"⚠️ [Background task] Email service returned False for enterprise: {user.email}")
            except Exception as e:
                logger.error(f"❌ [Background task] Error sending welcome email to enterprise {user.email}: {e}")
                
    elif user_type == "individual":
        from app.models.individual import Individual
        from app.services.email_service_individual import IndividualEmailService
        
        with get_db_context() as db:
            user = db.query(Individual).filter(Individual.id == user_id).first()
            if not user:
                logger.error(f"❌ [Background task] Individual with ID {user_id} not found.")
                return
                
            try:
                service = IndividualEmailService(db)
                success = service.send_welcome_email(user)
                if success:
                    logger.info(f"✅ [Background task] Welcome email sent successfully to individual: {user.email}")
                else:
                    logger.warning(f"⚠️ [Background task] Email service returned False for individual: {user.email}")
            except Exception as e:
                logger.error(f"❌ [Background task] Error sending welcome email to individual {user.email}: {e}")
    else:
        logger.error(f"❌ [Background task] Unknown user_type: {user_type}")
