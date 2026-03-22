"""Initial schema — all tables + PostGIS indexes

Revision ID: 0001
Revises:
Create Date: 2026-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ── analysis_regions ──────────────────────────────────────────────────────
    op.create_table(
        "analysis_regions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "bbox",
            geoalchemy2.types.Geometry(geometry_type="POLYGON", srid=4326),
            nullable=False,
        ),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("grid_res_km", sa.Numeric(5, 2), nullable=False, server_default="5.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("cache_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_regions_bbox",
        "analysis_regions",
        ["bbox"],
        postgresql_using="gist",
    )

    # ── location_scores ───────────────────────────────────────────────────────
    op.create_table(
        "location_scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("region_id", sa.String(36), sa.ForeignKey("analysis_regions.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "point",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326),
            nullable=False,
        ),
        sa.Column(
            "cell_polygon",
            geoalchemy2.types.Geometry(geometry_type="POLYGON", srid=4326),
            nullable=True,
        ),
        sa.Column("composite_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("score_power", sa.Numeric(5, 4), nullable=True),
        sa.Column("score_water", sa.Numeric(5, 4), nullable=True),
        sa.Column("score_geological", sa.Numeric(5, 4), nullable=True),
        sa.Column("score_climate", sa.Numeric(5, 4), nullable=True),
        sa.Column("score_connectivity", sa.Numeric(5, 4), nullable=True),
        sa.Column("score_economic", sa.Numeric(5, 4), nullable=True),
        sa.Column("score_environmental", sa.Numeric(5, 4), nullable=True),
        sa.Column("metrics", postgresql.JSONB, nullable=True),
        sa.Column("composite_detail", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_scores_point", "location_scores", ["point"], postgresql_using="gist")
    op.create_index("idx_scores_region", "location_scores", ["region_id"])
    op.create_index(
        "idx_scores_composite",
        "location_scores",
        [sa.text("composite_score DESC")],
    )

    # ── layer_cache ───────────────────────────────────────────────────────────
    op.create_table(
        "layer_cache",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("region_id", sa.String(36), sa.ForeignKey("analysis_regions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("layer_id", sa.String(50), nullable=False),
        sa.Column("geojson", postgresql.JSONB, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("region_id", "layer_id", name="uq_layer_cache_region_layer"),
    )

    # ── land_listings ─────────────────────────────────────────────────────────
    op.create_table(
        "land_listings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("external_id", sa.String(200), nullable=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column(
            "point",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
        sa.Column(
            "polygon",
            geoalchemy2.types.Geometry(geometry_type="MULTIPOLYGON", srid=4326),
            nullable=True,
        ),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("county", sa.String(100), nullable=True),
        sa.Column("acres", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_usd", sa.Integer, nullable=True),
        sa.Column("price_per_acre", sa.Numeric(12, 2), nullable=True),
        sa.Column("zoning", sa.String(200), nullable=True),
        sa.Column("listing_url", sa.Text, nullable=True),
        sa.Column("raw_data", postgresql.JSONB, nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_listings_point", "land_listings", ["point"], postgresql_using="gist")
    op.create_index("idx_listings_state", "land_listings", ["state"])


def downgrade() -> None:
    op.drop_table("land_listings")
    op.drop_table("layer_cache")
    op.drop_table("location_scores")
    op.drop_table("analysis_regions")
    op.execute("DROP EXTENSION IF EXISTS postgis")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
