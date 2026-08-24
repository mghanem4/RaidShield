"""Add transparent content-review evidence metadata.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # 0001 uses metadata.create_all, so a fresh database may already contain a
    # column introduced in the current model. Existing installations do not.
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("alerts")}
    if "content_review_evidence" not in columns:
        op.add_column("alerts", sa.Column("content_review_evidence", sa.JSON(), nullable=True))


def downgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("alerts")}
    if "content_review_evidence" in columns:
        op.drop_column("alerts", "content_review_evidence")
