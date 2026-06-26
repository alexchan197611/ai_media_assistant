"""Add segment background focal position."""

from alembic import op
import sqlalchemy as sa

revision = "0003_segment_background_position"
down_revision = "0002_jobs_assets_project_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("segments") as batch:
        batch.add_column(sa.Column("background_position_x", sa.Float(), nullable=False, server_default="0.5"))
        batch.add_column(sa.Column("background_position_y", sa.Float(), nullable=False, server_default="0.5"))


def downgrade() -> None:
    with op.batch_alter_table("segments") as batch:
        batch.drop_column("background_position_y")
        batch.drop_column("background_position_x")
