"""Initial V2 Unified Migration

Revision ID: 000000000000
Revises: None
Create Date: 2026-04-04 13:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '000000000000'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # 1. TABLE: tenders
    op.create_table(
        'tenders',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('sector', sa.String(length=255), nullable=True),
        sa.Column('estimated_budget', sa.Float(), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('source_country', sa.String(length=10), nullable=True, server_default='GN'),
        sa.Column('deadline', sa.DateTime(), nullable=True),
        sa.Column('source_url', sa.String(length=1000), nullable=False),
        sa.Column('pdf_path', sa.String(length=500), nullable=True),
        sa.Column('is_analyzed', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_url')
    )
    op.create_index('ix_tenders_id', 'tenders', ['id'], unique=False)
    op.create_index('ix_tenders_title', 'tenders', ['title'], unique=False)
    op.create_index('ix_tenders_sector', 'tenders', ['sector'], unique=False)
    op.create_index('ix_tenders_is_analyzed', 'tenders', ['is_analyzed'], unique=False)

    # 2. TABLE: enterprises
    op.create_table(
        'enterprises',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('sector', sa.String(length=255), nullable=False),
        sa.Column('min_budget', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('max_budget', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('zones', sa.Text(), nullable=True),
        sa.Column('experience_years', sa.Integer(), server_default='0', nullable=False),
        sa.Column('technical_capacity', sa.Text(), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('specific_keywords', sa.Text(), nullable=True),
        sa.Column('exclude_keywords', sa.Text(), nullable=True),
        sa.Column('logo_url', sa.String(length=500), nullable=True),
        sa.Column('subscription_plan', sa.String(length=20), server_default='PASS', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_enterprises_id', 'enterprises', ['id'], unique=False)
    op.create_index('ix_enterprises_name', 'enterprises', ['name'], unique=False)
    op.create_index('ix_enterprises_sector', 'enterprises', ['sector'], unique=False)

    # 3. TABLE: individuals
    op.create_table(
        'individuals',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('whatsapp', sa.String(length=50), nullable=True),
        sa.Column('country', sa.String(length=100), server_default=sa.text("'Guinée'"), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=False),
        sa.Column('skills', sa.Text(), nullable=False),
        sa.Column('experience_level', sa.String(length=20), nullable=False),
        sa.Column('experience_years', sa.Integer(), server_default='0', nullable=True),
        sa.Column('mission_type', sa.String(length=20), nullable=False),
        sa.Column('desired_rate', sa.Float(), nullable=True),
        sa.Column('languages', sa.String(length=50), nullable=False),
        sa.Column('portfolio_url', sa.String(length=500), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('exclude_keywords', sa.Text(), nullable=True),
        sa.Column('subscription_plan', sa.String(length=20), server_default='PASS', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_individuals_id', 'individuals', ['id'], unique=False)
    op.create_index('ix_individuals_email', 'individuals', ['email'], unique=False)

    # 4. TABLE: analyses
    op.create_table(
        'analyses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tender_id', sa.Integer(), nullable=False),
        sa.Column('enterprise_id', sa.Integer(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('score', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('extracted_sector', sa.Text(), nullable=True),
        sa.Column('extracted_budget', sa.Float(), nullable=True),
        sa.Column('extracted_location', sa.Text(), nullable=True),
        sa.Column('extracted_deadline', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['enterprise_id'], ['enterprises.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tender_id')
    )
    op.create_index('ix_analyses_id', 'analyses', ['id'], unique=False)
    op.create_index('ix_analyses_tender_id', 'analyses', ['tender_id'], unique=False)
    op.create_index('ix_analyses_enterprise_id', 'analyses', ['enterprise_id'], unique=False)

    # 5. TABLE: subscriptions
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('enterprise_id', sa.Integer(), nullable=False),
        sa.Column('plan', sa.String(length=20), server_default='PASS', nullable=False),
        sa.Column('max_sectors', sa.Integer(), server_default='3', nullable=False),
        sa.Column('price_gnf', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['enterprise_id'], ['enterprises.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_subscriptions_id', 'subscriptions', ['id'], unique=False)
    op.create_index('ix_subscriptions_enterprise_id', 'subscriptions', ['enterprise_id'], unique=False)
    op.create_index('ix_subscriptions_is_active', 'subscriptions', ['is_active'], unique=False)

    # 6. TABLE: email_logs
    op.create_table(
        'email_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('enterprise_id', sa.Integer(), nullable=True),
        sa.Column('individual_id', sa.Integer(), nullable=True),
        sa.Column('tender_id', sa.Integer(), nullable=True),
        sa.Column('recipient_email', sa.String(length=255), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='pending', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['enterprise_id'], ['enterprises.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['individual_id'], ['individuals.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tender_id'], ['tenders.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_email_logs_id', 'email_logs', ['id'], unique=False)
    op.create_index('ix_email_logs_enterprise_id', 'email_logs', ['enterprise_id'], unique=False)
    op.create_index('ix_email_logs_individual_id', 'email_logs', ['individual_id'], unique=False)


def downgrade():
    op.drop_table('email_logs')
    op.drop_table('subscriptions')
    op.drop_table('analyses')
    op.drop_table('individuals')
    op.drop_table('enterprises')
    op.drop_table('tenders')
