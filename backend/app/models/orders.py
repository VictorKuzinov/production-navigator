# orders.py
from app.db.database import Base
from app.models.base_reference import PNCBaseReference


class OrderType(Base, PNCBaseReference):
    __tablename__ = "pnc_order_type"