# products.py

from app.db.database import Base
from app.models.base_reference import PNCBaseReference


class ProductType(Base, PNCBaseReference):
    __tablename__ = "pnc_product_type"