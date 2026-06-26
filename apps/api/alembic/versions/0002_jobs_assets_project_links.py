"""Add project links to assets and job targets/results."""

from alembic import op
import sqlalchemy as sa

revision = "0002_jobs_assets_project_links"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("assets") as batch:
        batch.add_column(sa.Column("project_id", sa.String(length=36), nullable=True))
        batch.create_index("ix_assets_project_id", ["project_id"])
        batch.create_foreign_key("fk_assets_project_id_projects", "projects", ["project_id"], ["id"], ondelete="CASCADE")

    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("target_segment_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("result_asset_id", sa.String(length=36), nullable=True))
        batch.create_index("ix_jobs_target_segment_id", ["target_segment_id"])
        batch.create_foreign_key("fk_jobs_result_asset_id_assets", "assets", ["result_asset_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.drop_constraint("fk_jobs_result_asset_id_assets", type_="foreignkey")
        batch.drop_index("ix_jobs_target_segment_id")
        batch.drop_column("result_asset_id")
        batch.drop_column("target_segment_id")

    with op.batch_alter_table("assets") as batch:
        batch.drop_constraint("fk_assets_project_id_projects", type_="foreignkey")
        batch.drop_index("ix_assets_project_id")
        batch.drop_column("project_id")
