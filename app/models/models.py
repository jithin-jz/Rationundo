from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base
from app.worker.time_utils import now_ist_naive


class Pincode(Base):
    __tablename__ = "pincodes"

    id = Column(Integer, primary_key=True)
    pincode = Column(String(6), nullable=False, index=True)
    post_office_name = Column(String(200), nullable=False)
    district = Column(String(100), nullable=False)
    region = Column(String(200))
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    shops = relationship("RationShop", back_populates="pincode_rel")

    __table_args__ = (
        Index(
            "idx_pincode_trgm",
            "post_office_name",
            postgresql_using="gin",
            postgresql_ops={"post_office_name": "gin_trgm_ops"},
        ),
    )


class RationShop(Base):
    __tablename__ = "ration_shops"

    id = Column(Integer, primary_key=True)
    ard_number = Column(String(50), nullable=False, unique=True)
    dealer_name = Column(String(300))
    district = Column(String(100), nullable=False)
    tso_code = Column(String(50), nullable=False)
    location_raw_string = Column(Text)
    local_place = Column(String(120), nullable=True)
    pincode_id = Column(Integer, ForeignKey("pincodes.id"), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    pincode_rel = relationship("Pincode", back_populates="shops")
    stock_statuses = relationship("ShopStockStatus", back_populates="shop")

    __table_args__ = (
        Index("idx_shop_tso", "tso_code"),
        Index("idx_shop_district", "district"),
        # Speeds up the "near me" bounding-box prefilter before haversine.
        Index("idx_shop_latlon", "latitude", "longitude"),
    )


class ShopStockStatus(Base):
    __tablename__ = "shop_stock_status"

    id = Column(Integer, primary_key=True)
    shop_id = Column(Integer, ForeignKey("ration_shops.id"), nullable=False)
    last_checked_timestamp = Column(DateTime, default=now_ist_naive)
    is_stock_delivered = Column(Boolean, default=False)
    month_cycle = Column(String(20), nullable=False)  # e.g. "May 2026"

    shop = relationship("RationShop", back_populates="stock_statuses")
    items = relationship("StockItem", back_populates="stock_status", cascade="all, delete-orphan")

    __table_args__ = (Index("idx_shop_month", "shop_id", "month_cycle", unique=True),)


class StockItem(Base):
    __tablename__ = "stock_items"

    id = Column(Integer, primary_key=True)
    stock_status_id = Column(Integer, ForeignKey("shop_stock_status.id"), nullable=False)
    commodity_name = Column(String(200), nullable=False)
    allocated_quantity = Column(Float, default=0.0)
    received_quantity = Column(Float, default=0.0)
    arrival_timestamp = Column(DateTime, nullable=True)

    stock_status = relationship("ShopStockStatus", back_populates="items")

    __table_args__ = (Index("idx_stockitem_status", "stock_status_id"),)
