"""add tso_code and district indexes on ration_shops

Revision ID: a1b2c3d4e5f6
Revises: 29bbdbd8d410
Create Date: 2026-05-31 11:15:00.000000

"""
from typing import Sequence, Union
from alembic import op


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '29bbdbd8d410'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('idx_shop_tso', 'ration_shops', ['tso_code'], unique=False)
    op.create_index('idx_shop_district', 'ration_shops', ['district'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_shop_district', table_name='ration_shops')
    op.drop_index('idx_shop_tso', table_name='ration_shops')
