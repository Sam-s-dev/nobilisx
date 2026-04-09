# app/routers/auth.py
"""
Endpoints d'authentification et de validation (Trial check)
"""

import logging
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.enterprise import Enterprise
from app.models.individual import Individual

from app.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Auth & Validation"],
)

@router.get("/check-trial/{email}")
@limiter.limit("10/minute")
def check_trial_availability(request: Request, email: str, db: Session = Depends(get_db)):
    """
    Vérifie si un email a déjà bénéficié d'un essai gratuit.
    Recherche dans les deux segments (Entreprises et Particuliers).
    """
    # 1. Check in Enterprises
    ent = db.query(Enterprise).filter(Enterprise.email == email).first()
    if ent:
        # If they already have a PASS plan (even if expired)
        return {"available": False, "reason": "Compte entreprise existant", "user_type": "enterprise"}
    
    # 2. Check in Individuals
    ind = db.query(Individual).filter(Individual.email == email).first()
    if ind:
        return {"available": False, "reason": "Compte particulier existant", "user_type": "individual"}
    
    return {"available": True}
