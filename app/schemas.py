from datetime import datetime
from pydantic import BaseModel


class PincodeResult(BaseModel):
    id: int
    pincode: str
    post_office_name: str
    district: str

    class Config:
        from_attributes = True


class Suggestion(BaseModel):
    type: str  # "place" or "shop"
    id: int
    label: str
    sublabel: str


class StockItemOut(BaseModel):
    commodity_name: str
    allocated_quantity: float
    received_quantity: float
    arrival_timestamp: datetime | None

    class Config:
        from_attributes = True


class ShopStatusOut(BaseModel):
    ard_number: str
    dealer_name: str | None
    district: str
    location: str | None
    is_stock_delivered: bool
    delivery_state: str = "none"  # "full" | "partial" | "none"
    last_checked: datetime | None
    month_cycle: str
    items: list[StockItemOut]

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    pincode: str
    post_office_name: str
    shops: list[ShopStatusOut]
