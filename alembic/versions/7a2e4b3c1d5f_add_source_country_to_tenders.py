"""Add source_country to tenders

Revision ID: 7a2e4b3c1d5f
Revises: 36802134ef6e
Create Date: 2024-04-02 12:11:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a2e4b3c1d5f'
down_revision = '36802134ef6e'
branch_labels = None
depends_on = None


def upgrade():
    # Ajout de la colonne source_country avec une valeur par défaut "GN" (Guinée)
    # Le server_default est indispensable pour les lignes déjà existantes en base.
    op.add_column('tenders', 
        sa.Column('source_country', sa.String(length=10), nullable=True, server_default='GN')
    )


def downgrade():
    op.drop_column('tenders', 'source_country')
