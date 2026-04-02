# app/routers/individuals.py
"""
Endpoints pour la gestion des particuliers (Segment Particuliers V2)
CRUD complet + email de bienvenue automatique à l'inscription.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.individual import Individual
from app.schemas.individual import IndividualCreate, IndividualResponse, IndividualUpdate
from app.services.email_service_individual import IndividualEmailService

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
def create_individual(
    data: IndividualCreate,
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
    if client_plan in ["ENTRY", "ELITE"]:
        payload["subscription_plan"] = f"PENDING_{client_plan}"
    else:
        payload["subscription_plan"] = "PASS"

    individual = Individual(**payload)
    db.add(individual)
    db.commit()
    db.refresh(individual)

    logger.info(
        f"👤 Particulier inscrit: {individual.full_name} "
        f"(id={individual.id}, plan={payload['subscription_plan']}, domaine={individual.domain})"
    )

    # Envoi de l'email de bienvenue
    try:
        email_service = IndividualEmailService(db)
        email_service.send_welcome_email(individual)
    except Exception as e:
        logger.error(f"❌ Erreur envoi email bienvenue (individual): {e}")

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
