from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PincodeResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pincode: str
    post_office_name: str
    district: str


class Suggestion(BaseModel):
    type: str  # "place" or "shop"
    id: int
    label: str
    sublabel: str


class StockItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    commodity_name: str
    allocated_quantity: float
    received_quantity: float
    arrival_timestamp: datetime | None


class ShopStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ard_number: str
    dealer_name: str | None
    district: str
    location: str | None
    local_place: str | None = None
    is_stock_delivered: bool
    delivery_state: str = "none"  # "full" | "partial" | "none"
    last_checked: datetime | None
    month_cycle: str
    items: list[StockItemOut]
    latitude: float | None = None
    longitude: float | None = None
    distance_km: float | None = None


class SearchResponse(BaseModel):
    pincode: str
    post_office_name: str
    shops: list[ShopStatusOut]
