# app/routers/admin.py
"""
Router Administration - Validation des paiements Orange Money
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.enterprise import Enterprise
from app.models.individual import Individual
from app.services.email_service import EmailService
from app.services.email_service_individual import IndividualEmailService
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(
    prefix="/admin",
    tags=["Administration"],
)

def verify_admin(x_admin_password: Optional[str] = Header(None)):
    """Vérifie le mot de passe admin dans les headers"""
    if not x_admin_password or x_admin_password != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Accès non autorisé : Mot de passe admin incorrect.")
    return True

@router.get("/pending")
def list_pending_users(
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_admin)
):
    """Liste tous les utilisateurs en attente de validation (Entreprises et Particuliers)"""
    
    # 1. Entreprises
    pending_ents = db.query(Enterprise).filter(
        Enterprise.subscription_plan.like("PENDING_%")
    ).all()
    
    # 2. Particuliers
    pending_inds = db.query(Individual).filter(
        Individual.subscription_plan.like("PENDING_%")
    ).all()
    
    # Formater pour le frontend
    results = []
    
    for ent in pending_ents:
        results.append({
            "id": ent.id,
            "type": "enterprise",
            "name": ent.name,
            "email": ent.email,
            "plan_requested": ent.subscription_plan.replace("PENDING_", ""),
            "created_at": ent.created_at.isoformat()
        })
        
    for ind in pending_inds:
        results.append({
            "id": ind.id,
            "type": "individual",
            "name": ind.full_name,
            "email": ind.email,
            "plan_requested": ind.subscription_plan.replace("PENDING_", ""),
            "created_at": ind.created_at.isoformat()
        })
        
    # Trier par date (plus récent en haut)
    results.sort(key=lambda x: x["created_at"], reverse=True)
    return results

@router.post("/validate")
def validate_user_payment(
    email: str,
    user_type: str, # 'enterprise' or 'individual'
    db: Session = Depends(get_db),
    authorized: bool = Depends(verify_admin)
):
    """Valide le paiement d'un utilisateur et envoie l'email de confirmation"""
    
    if user_type == "enterprise":
        user = db.query(Enterprise).filter(Enterprise.email == email).first()
        service = EmailService(db)
    else:
        user = db.query(Individual).filter(Individual.email == email).first()
        service = IndividualEmailService(db)
        
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé.")
        
    if not user.subscription_plan.startswith("PENDING_"):
        return {"message": "L'utilisateur est déjà actif ou n'a pas de paiement en attente.", "plan": user.subscription_plan}
        
    # 1. Retirer le préfixe PENDING_
    old_plan = user.subscription_plan
    new_plan = old_plan.replace("PENDING_", "")
    user.subscription_plan = new_plan
    
    db.commit()
    logger.info(f"✅ Paiement validé pour {email} ({user_type}). Plan: {new_plan}")
    
    # 2. Envoyer l'email de confirmation (Réutilise welcome_email qui gère le contenu selon le plan)
    try:
        service.send_welcome_email(user)
        email_sent = True
    except Exception as e:
        logger.error(f"❌ Erreur envoi email confirmation à {email}: {e}")
        email_sent = False
        
    return {
        "status": "success",
        "message": f"Utilisateur {email} validé avec succès sur le plan {new_plan}.",
        "email_sent": email_sent
    }

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
