"""sync_models

Revision ID: 628b459dbe96
Revises: 000000000000
Create Date: 2026-06-21 22:23:33.526310

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '628b459dbe96'
down_revision: Union[str, Sequence[str], None] = '000000000000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add missing columns to enterprises
    op.add_column('enterprises', sa.Column('logo_data', sa.Text(), nullable=True, comment='Contenu Base64 du logo'))
    op.add_column('enterprises', sa.Column('subscription_expires_at', sa.DateTime(), nullable=True, comment="Date d'expiration"))
    op.add_column('enterprises', sa.Column('consent_terms', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('enterprises', sa.Column('consent_marketing', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('enterprises', sa.Column('consent_timestamp', sa.DateTime(), nullable=True))

    # 2. Add missing columns to individuals
    op.add_column('individuals', sa.Column('logo_data', sa.Text(), nullable=True, comment='Contenu Base64 du logo'))
    op.add_column('individuals', sa.Column('subscription_expires_at', sa.DateTime(), nullable=True, comment="Date d'expiration"))
    op.add_column('individuals', sa.Column('consent_terms', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('individuals', sa.Column('consent_marketing', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('individuals', sa.Column('consent_timestamp', sa.DateTime(), nullable=True))

    # 3. Add missing columns and constraints to subscriptions
    op.add_column('subscriptions', sa.Column('individual_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_subscriptions_individual', 'subscriptions', 'individuals', ['individual_id'], ['id'], ondelete='CASCADE')
    op.create_index(op.f('ix_subscriptions_individual_id'), 'subscriptions', ['individual_id'], unique=False)
    
    op.alter_column('subscriptions', 'enterprise_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('subscriptions', 'price_gnf',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               comment='Prix paye en GNF',
               existing_comment='Prix en GNF/mois',
               existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Drop foreign key, index and columns from subscriptions
    op.drop_index(op.f('ix_subscriptions_individual_id'), table_name='subscriptions')
    op.drop_constraint('fk_subscriptions_individual', 'subscriptions', type_='foreignkey')
    op.drop_column('subscriptions', 'individual_id')
    
    op.alter_column('subscriptions', 'price_gnf',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               comment='Prix en GNF/mois',
               existing_comment='Prix paye en GNF',
               existing_nullable=False)
    op.alter_column('subscriptions', 'enterprise_id',
               existing_type=sa.INTEGER(),
               nullable=False)

    # 2. Drop columns from individuals
    op.drop_column('individuals', 'consent_timestamp')
    op.drop_column('individuals', 'consent_marketing')
    op.drop_column('individuals', 'consent_terms')
    op.drop_column('individuals', 'subscription_expires_at')
    op.drop_column('individuals', 'logo_data')

    # 3. Drop columns from enterprises
    op.drop_column('enterprises', 'consent_timestamp')
    op.drop_column('enterprises', 'consent_marketing')
    op.drop_column('enterprises', 'consent_terms')
    op.drop_column('enterprises', 'subscription_expires_at')
    op.drop_column('enterprises', 'logo_data')
