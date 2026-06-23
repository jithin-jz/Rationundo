"""add stock_items FK index and shop lat/lon index

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-23 18:40:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # selectinload(...).items issues `WHERE stock_status_id IN (...)`; index the FK.
    op.create_index(
        'idx_stockitem_status', 'stock_items', ['stock_status_id'], unique=False
    )
    # Bounding-box prefilter for the "near me" haversine search.
    op.create_index(
        'idx_shop_latlon', 'ration_shops', ['latitude', 'longitude'], unique=False
    )


def downgrade() -> None:
    op.drop_index('idx_shop_latlon', table_name='ration_shops')
    op.drop_index('idx_stockitem_status', table_name='stock_items')
