"""Add individual model and update email logs

Revision ID: 36802134ef6e
Revises: 
Create Date: 2026-04-02 11:07:45.123456

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '36802134ef6e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Création de la table individuals
    op.create_table(
        'individuals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('country', sa.String(length=100), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=False),
        sa.Column('skills', sa.Text(), nullable=False),
        sa.Column('experience_level', sa.String(length=20), nullable=False),
        sa.Column('experience_years', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('mission_type', sa.String(length=20), nullable=False),
        sa.Column('desired_rate', sa.Float(), nullable=True),
        sa.Column('languages', sa.String(length=50), nullable=False),
        sa.Column('portfolio_url', sa.String(length=500), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('exclude_keywords', sa.Text(), nullable=True),
        sa.Column('subscription_plan', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_individuals_id'), 'individuals', ['id'], unique=False)
    op.create_index(op.f('ix_individuals_email'), 'individuals', ['email'], unique=False)

    # 2. Mise à jour de email_logs
    # On passe enterprise_id en nullable
    op.alter_column('email_logs', 'enterprise_id',
               existing_type=sa.INTEGER(),
               nullable=True,
               existing_server_default=None)
    
    # On ajoute individual_id
    op.add_column('email_logs', sa.Column('individual_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_email_logs_individual_id_individuals', 'email_logs', 'individuals', ['individual_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_email_logs_individual_id'), 'email_logs', ['individual_id'], unique=False)


def downgrade() -> None:
    # 1. Suppression de email_logs changes
    op.drop_index(op.f('ix_email_logs_individual_id'), table_name='email_logs')
    op.drop_constraint('fk_email_logs_individual_id_individuals', 'email_logs', type_='foreignkey')
    op.drop_column('email_logs', 'individual_id')
    op.alter_column('email_logs', 'enterprise_id',
               existing_type=sa.INTEGER(),
               nullable=False)

    # 2. Suppression de la table individuals
    op.drop_index(op.f('ix_individuals_email'), table_name='individuals')
    op.drop_index(op.f('ix_individuals_id'), table_name='individuals')
    op.drop_table('individuals')
