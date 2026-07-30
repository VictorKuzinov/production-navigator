# enterprises.py
from app.db.database import Base
from app.models.base_reference import PNCBaseReference


class CertificateType(Base, PNCBaseReference):
    __tablename__ = "pnc_certificate_type"


class Industry(Base, PNCBaseReference):
    __tablename__ = "pnc_industry"