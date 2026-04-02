# app/schemas/individual.py
"""
Schémas Pydantic pour les particuliers (Segment Particuliers V2)
"""

from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from typing import Optional


class IndividualBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr = Field(..., description="Email pour recevoir les rapports")
    country: str = Field(..., max_length=100)
    domain: str = Field(..., description="Domaine principal (ex: Développement web)")
    skills: str = Field(..., description="Compétences (mots-clés séparés par virgules)")
    experience_level: str = Field(..., description="Débutant / Intermédiaire / Expert")
    experience_years: int = Field(0, ge=0)
    mission_type: str = Field(..., description="Court terme / Long terme / Les deux")
    desired_rate: Optional[float] = Field(None, ge=0, description="Tarif journalier souhaité en USD")
    languages: str = Field(..., description="FR / EN / FR+EN")
    portfolio_url: Optional[str] = Field(None, max_length=500)
    bio: Optional[str] = Field(None, description="Courte présentation 2–4 lignes")
    exclude_keywords: Optional[str] = Field(None, description="Mots-clés à exclure")
    subscription_plan: str = Field("PASS", description="PASS / ENTRY / ELITE")


class IndividualCreate(IndividualBase):
    """Schéma pour la création (inscription)"""
    pass


class IndividualUpdate(BaseModel):
    """Schéma pour la mise à jour partielle"""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    country: Optional[str] = None
    domain: Optional[str] = None
    skills: Optional[str] = None
    experience_level: Optional[str] = None
    experience_years: Optional[int] = None
    mission_type: Optional[str] = None
    desired_rate: Optional[float] = None
    languages: Optional[str] = None
    portfolio_url: Optional[str] = None
    bio: Optional[str] = None
    exclude_keywords: Optional[str] = None
    subscription_plan: Optional[str] = None


class IndividualResponse(IndividualBase):
    """Schéma pour la réponse API"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
