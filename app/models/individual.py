# app/models/individual.py
"""
Modèle SQLAlchemy pour les particuliers (Segment Particuliers V2)
"""

from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Individual(Base):
    __tablename__ = "individuals"

    # 1. id
    id = Column(Integer, primary_key=True, index=True)
    
    # 2. full_name
    full_name = Column(String(255), nullable=False)
    
    # 3. email
    email = Column(String(255), nullable=False, index=True)
    whatsapp = Column(String(50), nullable=True) # WhatsApp (+224...)
    
    # 4. country
    country = Column(String(100), nullable=False, default="Guinée")
    
    # 5. domain
    domain = Column(String(255), nullable=False)
    
    # 6. skills
    skills = Column(Text, nullable=False)
    
    # 7. experience_level
    experience_level = Column(String(20), nullable=False)
    
    # 8. experience_years
    experience_years = Column(Integer, default=0)
    
    # 9. mission_type
    mission_type = Column(String(20), nullable=False)
    
    # 10. desired_rate
    desired_rate = Column(Float, nullable=True)
    
    # 11. languages
    languages = Column(String(50), nullable=False)
    
    # 12. portfolio_url
    portfolio_url = Column(String(500), nullable=True)
    
    # 13. bio
    bio = Column(Text, nullable=True)
    
    # 14. exclude_keywords
    exclude_keywords = Column(Text, nullable=True)
    
    # 15. subscription_plan
    subscription_plan = Column(String(20), default="PASS", nullable=False)
    
    # 16. created_at
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 17. updated_at
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relation avec les logs emails
    email_logs = relationship("EmailLog", back_populates="individual")

    def __repr__(self):
        return f"<Individual(name={self.full_name}, email={self.email}, plan={self.subscription_plan})>"
