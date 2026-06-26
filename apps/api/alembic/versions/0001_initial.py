"""Initial project data model."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"; down_revision = None; branch_labels = None; depends_on = None

def upgrade():
    op.create_table("assets", sa.Column("id", sa.String(36), primary_key=True), sa.Column("kind", sa.String(32), nullable=False), sa.Column("original_name", sa.String(255), nullable=False), sa.Column("storage_path", sa.String(1024), nullable=False, unique=True), sa.Column("mime_type", sa.String(128), nullable=False), sa.Column("size", sa.Integer, nullable=False), sa.Column("duration_ms", sa.Integer), sa.Column("sha256", sa.String(64), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("projects", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("canvas", sa.JSON, nullable=False), sa.Column("template_id", sa.String(64), nullable=False), sa.Column("tts_settings", sa.JSON, nullable=False), sa.Column("bgm_settings", sa.JSON, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("segments", sa.Column("id", sa.String(36), primary_key=True), sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False), sa.Column("order", sa.Integer, nullable=False), sa.Column("text", sa.Text, nullable=False), sa.Column("marks", sa.JSON, nullable=False), sa.Column("text_color", sa.String(16)), sa.Column("background_asset_id", sa.String(36), sa.ForeignKey("assets.id", ondelete="SET NULL")), sa.Column("background_motion", sa.String(32)), sa.Column("tts_audio_asset_id", sa.String(36), sa.ForeignKey("assets.id", ondelete="SET NULL")), sa.Column("audio_duration_ms", sa.Integer), sa.Column("status", sa.String(32), nullable=False))
    op.create_table("jobs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False), sa.Column("type", sa.String(32), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("progress", sa.Float, nullable=False), sa.Column("stage", sa.String(128), nullable=False), sa.Column("error_code", sa.String(64)), sa.Column("error_message", sa.Text), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("finished_at", sa.DateTime(timezone=True)))

def downgrade():
    op.drop_table("jobs"); op.drop_table("segments"); op.drop_table("projects"); op.drop_table("assets")

