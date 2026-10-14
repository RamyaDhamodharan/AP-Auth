"""Create the users table."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    user_role = postgresql.ENUM(
        "associate",
        "admin",
        name="user_role",
        create_type=False,
    )

    # Create the enum only if it does not already exist.
    user_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "temp_password_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "failed_login_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "locked_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("users")

    postgresql.ENUM(
        "associate",
        "admin",
        name="user_role",
        create_type=False,
    ).drop(op.get_bind(), checkfirst=True)
