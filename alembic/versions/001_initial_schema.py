"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create media table
    op.create_table('media',
        sa.Column('id', postgresql.UUID(), nullable=False),
        sa.Column('type', sa.Enum('IMAGE', 'VIDEO', 'AUDIO', name='mediatype'), nullable=False),
        sa.Column('storage_path', sa.String(), nullable=False),
        sa.Column('storage_url', sa.String(), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(), nullable=True),
        sa.Column('file_extension', sa.String(), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('generation_model_name', sa.String(), nullable=True),
        sa.Column('generation_model_version', sa.String(), nullable=True),
        sa.Column('generation_params', sa.JSON(), nullable=True),
        sa.Column('storage_provider', sa.String(), nullable=False),
        sa.Column('bucket_name', sa.String(), nullable=True),
        sa.Column('etag', sa.String(), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_media_storage_path'), 'media', ['storage_path'], unique=False)
    
    # Create jobs table
    op.create_table('jobs',
        sa.Column('id', postgresql.UUID(), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELLED', 'RETRYING', name='jobstatus'), nullable=False),
        sa.Column('prompt', sa.String(), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=False),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('max_retries', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('error_details', sa.JSON(), nullable=True),
        sa.Column('celery_task_id', sa.String(), nullable=True),
        sa.Column('media_id', postgresql.UUID(), nullable=True),
        sa.Column('client_ip', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('request_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['media_id'], ['media.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_jobs_celery_task_id'), 'jobs', ['celery_task_id'], unique=False)
    op.create_index(op.f('ix_jobs_prompt'), 'jobs', ['prompt'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_jobs_prompt'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_celery_task_id'), table_name='jobs')
    op.drop_table('jobs')
    op.drop_index(op.f('ix_media_storage_path'), table_name='media')
    op.drop_table('media')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS jobstatus')
    op.execute('DROP TYPE IF EXISTS mediatype') 