# app/routers/individuals.py
"""
Endpoints pour la gestion des particuliers (Segment Particuliers V2)
CRUD complet + email de bienvenue automatique à l'inscription.
"""

import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session

from app.limiter import limiter

from app.database import get_db
from app.models.individual import Individual
from app.schemas.individual import IndividualCreate, IndividualResponse, IndividualUpdate
from app.services.email_service_individual import IndividualEmailService
from app.tasks import send_welcome_email_task

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/individuals",
    tags=["Particuliers"],
)


@router.post(
    "",
    response_model=IndividualResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Inscrire un particulier",
)
@limiter.limit("5/minute")
def create_individual(
    request: Request,
    data: IndividualCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Inscription d'un particulier avec envoi automatique d'un email de bienvenue.
    Si le plan choisi est ENTRY ou ELITE, le statut passe à PENDING_xxx
    jusqu'à confirmation du paiement Orange Money.
    """
    # Vérifier l'unicité de l'email
    existing = db.query(Individual).filter(Individual.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Un compte existe déjà avec l'email '{data.email}' (id={existing.id})",
        )

    payload = data.model_dump()

    # Gestion du statut en attente pour les plans payants
    client_plan = (payload.get("subscription_plan") or "PASS").upper()
    
    if client_plan == "PASS":
        # Vérifier si l'email a déjà été utilisé pour un compte (Entreprise ou Particulier)
        from app.models.enterprise import Enterprise
        already_ind = db.query(Individual).filter(Individual.email == payload["email"]).first()
        already_ent = db.query(Enterprise).filter(Enterprise.email == payload["email"]).first()
        if already_ind or already_ent:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Cet email a déjà bénéficié d'un essai gratuit ou d'un compte existant."
            )
        payload["subscription_plan"] = "PASS"
    elif client_plan in ["ENTRY", "ELITE"]:
        payload["subscription_plan"] = f"PENDING_{client_plan}"
    else:
        payload["subscription_plan"] = "PASS"

    # ── Calcul de l'expiration Nobilis ──
    client_plan_clean = client_plan.replace("PENDING_", "")
    duration = 7 if client_plan_clean == "PASS" else 365
    payload["subscription_expires_at"] = datetime.utcnow() + timedelta(days=duration)

    individual = Individual(**payload)
    db.add(individual)
    db.commit()
    db.refresh(individual)

    logger.info(
        f"👤 Particulier inscrit: {individual.full_name} "
        f"(id={individual.id}, plan={payload['subscription_plan']}, expires={payload['subscription_expires_at']})"
    )

    # Envoi de l'email de bienvenue en arrière-plan
    background_tasks.add_task(send_welcome_email_task, individual.id, "individual")

    return individual


@router.get(
    "",
    response_model=list[IndividualResponse],
    summary="Lister les particuliers",
)
def list_individuals(
    skip: int = 0,
    limit: int = 50,
    domain: str | None = None,
    country: str | None = None,
    db: Session = Depends(get_db),
):
    """Liste les particuliers inscrits avec filtres optionnels."""
    query = db.query(Individual)
    if domain:
        query = query.filter(Individual.domain.ilike(f"%{domain}%"))
    if country:
        query = query.filter(Individual.country.ilike(f"%{country}%"))
    return query.offset(skip).limit(limit).all()


@router.get(
    "/{individual_id}",
    response_model=IndividualResponse,
    summary="Détail d'un particulier",
)
def get_individual(individual_id: int, db: Session = Depends(get_db)):
    """Retourne le profil complet d'un particulier."""
    individual = db.query(Individual).get(individual_id)
    if not individual:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Particulier #{individual_id} non trouvé",
        )
    return individual


@router.put(
    "/{individual_id}",
    response_model=IndividualResponse,
    summary="Mettre à jour un particulier",
)
def update_individual(
    individual_id: int,
    update_data: IndividualUpdate,
    db: Session = Depends(get_db),
):
    """Mise à jour partielle du profil d'un particulier."""
    individual = db.query(Individual).get(individual_id)
    if not individual:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Particulier #{individual_id} non trouvé",
        )

    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(individual, field, value)

    db.commit()
    db.refresh(individual)
    logger.info(f"✏️ Particulier mis à jour: {individual.full_name} (id={individual.id})")
    return individual


@router.delete(
    "/{individual_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un particulier",
)
def delete_individual(individual_id: int, db: Session = Depends(get_db)):
    """Supprime un particulier de la base."""
    individual = db.query(Individual).get(individual_id)
    if not individual:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Particulier #{individual_id} non trouvé",
        )
    db.delete(individual)
    db.commit()
    logger.info(f"🗑️ Particulier supprimé: #{individual_id}")
