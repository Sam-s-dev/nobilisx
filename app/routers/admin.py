# app/routers/admin.py
"""
Router Administration - Validation des paiements Orange Money
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.enterprise import Enterprise
from app.models.individual import Individual
from app.services.email_service import EmailService
from app.services.email_service_individual import IndividualEmailService
from app.config import get_settings

from app.limiter import limiter
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(
    prefix="/admin",
    tags=["Administration"],
)

def verify_admin(x_admin_password: Optional[str] = Header(None, alias="X-Admin-Password")):
    """Vérifie le mot de passe admin dans les headers (robuste aux espaces)"""
    if not x_admin_password:
        logger.warning("❌ Tentative d'accès admin sans header X-Admin-Password")
        raise HTTPException(status_code=401, detail="Header d'authentification manquant.")
    
    # Nettoyage des espaces pour éviter les erreurs de copier-coller
    provided = x_admin_password.strip()
    expected = settings.ADMIN_PASSWORD.strip()
    
    if provided != expected:
        logger.warning(f"❌ Échec auth admin. Reçu: {len(provided)} chars, Attendu: {len(expected)} chars.")
        raise HTTPException(status_code=401, detail="Mot de passe admin incorrect.")
    
    return True

@router.get("/list")
@limiter.limit("20/minute")
def list_all_users(
    request: Request,
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_admin)
):
    """Liste TOUS les utilisateurs (Entreprises et Particuliers) avec leur statut"""
    
    # 1. Entreprises
    ents = db.query(Enterprise).all()
    
    # 2. Particuliers
    inds = db.query(Individual).all()
    
    # Formater pour le frontend
    results = []
    
    for ent in ents:
        plan = ent.subscription_plan or "PASS"
        if plan.startswith("PENDING_"):
            status = "pending"
        elif plan.startswith("SUSPENDED_"):
            status = "suspended"
        else:
            status = "active"
            
        results.append({
            "id": ent.id,
            "type": "enterprise",
            "name": ent.name,
            "email": ent.email,
            "plan": plan.replace("PENDING_", "").replace("SUSPENDED_", ""),
            "status": status,
            "created_at": ent.created_at.isoformat() if ent.created_at else None,
            "expires_at": ent.subscription_expires_at.isoformat() if ent.subscription_expires_at else None
        })
        
    for ind in inds:
        plan = ind.subscription_plan or "PASS"
        if plan.startswith("PENDING_"):
            status = "pending"
        elif plan.startswith("SUSPENDED_"):
            status = "suspended"
        else:
            status = "active"
            
        results.append({
            "id": ind.id,
            "type": "individual",
            "name": ind.full_name,
            "email": ind.email,
            "plan": plan.replace("PENDING_", "").replace("SUSPENDED_", ""),
            "status": status,
            "created_at": ind.created_at.isoformat() if ind.created_at else None,
            "expires_at": ind.subscription_expires_at.isoformat() if ind.subscription_expires_at else None
        })
        
    # Trier par date (plus récent en haut)
    results.sort(key=lambda x: (x["created_at"] or ""), reverse=True)
    return results

@router.post("/validate")
@limiter.limit("5/minute")
def validate_user_payment(
    request: Request,
    email: str,
    user_type: str, # 'enterprise' or 'individual'
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_admin)
):
    """Valide ou Rétablit un compte utilisateur"""
    
    if user_type == "enterprise":
        user = db.query(Enterprise).filter(Enterprise.email == email).first()
        service = EmailService(db)
    else:
        user = db.query(Individual).filter(Individual.email == email).first()
        from app.services.email_service_individual import IndividualEmailService
        service = IndividualEmailService(db)
        
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé.")
        
    # Retirer les préfixes de blocage
    old_plan = user.subscription_plan
    new_plan = old_plan.replace("PENDING_", "").replace("SUSPENDED_", "")
    
    if old_plan == new_plan and new_plan != "PASS":
        return {"message": "L'utilisateur est déjà actif.", "plan": new_plan}
        
    user.subscription_plan = new_plan
    
    # Extension de l'abonnement (1 an / 365 jours)
    # Si le compte n'est pas encore expiré, on ajoute un an à la date de fin
    now = datetime.utcnow()
    duration = timedelta(days=365)
    
    if user.subscription_expires_at and user.subscription_expires_at > now:
        user.subscription_expires_at += duration
    else:
        user.subscription_expires_at = now + duration
    
    db.commit()
    
    logger.info(f"✅ Compte activé/rétabli pour {email} ({user_type}). Plan: {new_plan}. Expire: {user.subscription_expires_at}")
    
    # Envoyer l'email de bienvenue/confirmation
    email_sent = False
    try:
        service.send_welcome_email(user)
        email_sent = True
    except Exception as e:
        logger.error(f"❌ Erreur email confirmation à {email}: {e}")
        
    return {
        "status": "success",
        "message": f"Utilisateur {email} prêt sur le plan {new_plan}.",
        "email_sent": email_sent
    }

@router.post("/suspend")
def suspend_user(
    email: str,
    user_type: str,
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_admin)
):
    """Suspend un compte utilisateur (bloque les rapports)"""
    if user_type == "enterprise":
        user = db.query(Enterprise).filter(Enterprise.email == email).first()
    else:
        user = db.query(Individual).filter(Individual.email == email).first()
        
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé.")
        
    if user.subscription_plan.startswith("SUSPENDED_"):
        return {"message": "Déjà suspendu."}
        
    user.subscription_plan = f"SUSPENDED_{user.subscription_plan.replace('PENDING_', '')}"
    db.commit()
    
    logger.info(f"🚫 Compte suspendu pour {email} ({user_type})")
    return {"status": "success", "message": f"Compte {email} suspendu."}

@router.delete("/user")
def delete_user(
    email: str,
    user_type: str,
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_admin)
):
    """Supprime un utilisateur (refus ou erreur d'inscription)"""
    if user_type == "enterprise":
        user = db.query(Enterprise).filter(Enterprise.email == email).first()
    else:
        user = db.query(Individual).filter(Individual.email == email).first()
        
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé.")
        
    db.delete(user)
    db.commit()
    return {"message": f"Utilisateur {email} supprimé avec succès."}
