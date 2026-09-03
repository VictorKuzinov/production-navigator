import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictBool,
    StrictInt,
    TypeAdapter,
    field_validator,
    model_validator,
)

from app.models.procurement_opportunities import (
    ProcurementOpportunityStatus,
    RequirementStrength,
)

SOURCE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,49}$")
REFERENCE_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,49}$")
NORMALIZED_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
OKPD2_PATTERN = re.compile(r"^\d{2}\.\d{2}\.\d{2}\.\d{3}$")
HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)

MoneyDecimal = Annotated[
    Decimal,
    Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False),
]
QuantityDecimal = Annotated[
    Decimal,
    Field(gt=0, max_digits=18, decimal_places=6, allow_inf_nan=False),
]
PositiveDecimal3 = Annotated[
    Decimal,
    Field(gt=0, max_digits=18, decimal_places=3, allow_inf_nan=False),
]
PositiveDecimal4 = Annotated[
    Decimal,
    Field(gt=0, max_digits=18, decimal_places=4, allow_inf_nan=False),
]
Deadline = date | datetime | None


def _require_decimal_string(value: object) -> object:
    if value is not None and not isinstance(value, str):
        raise ValueError("Decimal values must be represented as JSON strings.")
    return value


def _trim_required(value: object, field_name: str) -> object:
    if isinstance(value, str):
        value = value.strip()
        if not value:
            raise ValueError(f"{field_name} must not be blank.")
    return value


def _trim_optional(value: object, field_name: str) -> object:
    if isinstance(value, str):
        value = value.strip()
        if not value:
            raise ValueError(f"{field_name} must be null or nonblank.")
    return value


def _normalize_reference_code(value: object, field_name: str) -> object:
    value = _trim_required(value, field_name)
    if isinstance(value, str) and not REFERENCE_CODE_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} has an invalid reference code format.")
    return value


def _normalize_deadline(value: Deadline) -> Deadline:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Datetime deadlines must include a timezone offset.")
        return value.astimezone(UTC)
    return value


class MaterialRequirementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_group_code: str = Field(min_length=1, max_length=50)
    material_id: StrictInt | None = Field(default=None, gt=0)
    requirement_strength: RequirementStrength

    @field_validator("material_group_code", mode="before")
    @classmethod
    def normalize_material_group_code(cls, value: object) -> object:
        return _normalize_reference_code(value, "material_group_code")


class TechnologyRequirementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    technology_code: str = Field(min_length=1, max_length=50)
    requirement_strength: RequirementStrength

    @field_validator("technology_code", mode="before")
    @classmethod
    def normalize_technology_code(cls, value: object) -> object:
        return _normalize_reference_code(value, "technology_code")


class EquipmentRequirementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    equipment_type_code: str = Field(min_length=1, max_length=50)
    cnc: StrictBool | None = None
    axes: StrictInt | None = Field(default=None, ge=1)
    working_zone_x_mm: PositiveDecimal3 | None = None
    working_zone_y_mm: PositiveDecimal3 | None = None
    working_zone_z_mm: PositiveDecimal3 | None = None
    diameter_mm: PositiveDecimal3 | None = None
    requirement_strength: RequirementStrength

    @field_validator("equipment_type_code", mode="before")
    @classmethod
    def normalize_equipment_type_code(cls, value: object) -> object:
        return _normalize_reference_code(value, "equipment_type_code")

    @field_validator(
        "working_zone_x_mm",
        "working_zone_y_mm",
        "working_zone_z_mm",
        "diameter_mm",
        mode="before",
    )
    @classmethod
    def require_decimal_strings(cls, value: object) -> object:
        return _require_decimal_string(value)


class DimensionalMassRequirementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    length_mm: PositiveDecimal3 | None = None
    width_mm: PositiveDecimal3 | None = None
    height_mm: PositiveDecimal3 | None = None
    diameter_mm: PositiveDecimal3 | None = None
    mass_kg: PositiveDecimal3 | None = None
    requirement_strength: RequirementStrength

    @field_validator(
        "length_mm",
        "width_mm",
        "height_mm",
        "diameter_mm",
        "mass_kg",
        mode="before",
    )
    @classmethod
    def require_decimal_strings(cls, value: object) -> object:
        return _require_decimal_string(value)

    @model_validator(mode="after")
    def require_domain_value(self) -> Self:
        if all(
            value is None
            for value in (
                self.length_mm,
                self.width_mm,
                self.height_mm,
                self.diameter_mm,
                self.mass_kg,
            )
        ):
            raise ValueError("A dimensional/mass block must contain a domain value.")
        return self


class QualityRequirementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_it_grade: StrictInt | None = Field(default=None, ge=1, le=18)
    maximum_ra_um: PositiveDecimal4 | None = None
    measuring_capability_required: StrictBool | None = None
    cmm_required: StrictBool | None = None
    requirement_strength: RequirementStrength

    @field_validator("maximum_ra_um", mode="before")
    @classmethod
    def require_decimal_string(cls, value: object) -> object:
        return _require_decimal_string(value)

    @model_validator(mode="after")
    def require_domain_value(self) -> Self:
        if all(
            value is None
            for value in (
                self.required_it_grade,
                self.maximum_ra_um,
                self.measuring_capability_required,
                self.cmm_required,
            )
        ):
            raise ValueError("A quality block must contain a domain value.")
        return self


class CertificateRequirementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    certificate_type_code: str = Field(min_length=1, max_length=50)
    requirement_strength: RequirementStrength
    required_by: date | None = None
    valid_through: date | None = None

    @field_validator("certificate_type_code", mode="before")
    @classmethod
    def normalize_certificate_type_code(cls, value: object) -> object:
        return _normalize_reference_code(value, "certificate_type_code")


class PreparedOpportunityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=50)
    external_id: str = Field(min_length=1, max_length=255)
    procurement_number: str | None = Field(default=None, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    customer: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=2048)
    status: ProcurementOpportunityStatus
    procurement_type: str | None = Field(default=None, max_length=50)

    okpd2_codes: list[str] | None
    product_type_codes: list[str] | None
    material_requirements: list[MaterialRequirementInput] | None
    technology_requirements: list[TechnologyRequirementInput] | None
    equipment_requirements: list[EquipmentRequirementInput] | None
    dimensional_mass_requirements: (
        Annotated[
            list[DimensionalMassRequirementInput],
            Field(max_length=1),
        ]
        | None
    )
    quality_requirements: (
        Annotated[
            list[QualityRequirementInput],
            Field(max_length=1),
        ]
        | None
    )
    required_certificates: list[CertificateRequirementInput] | None

    price_amount: MoneyDecimal | None = None
    price_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    region_code: str | None = Field(default=None, max_length=50)
    quantity: QuantityDecimal | None = None
    unit: str | None = Field(default=None, max_length=32)
    application_deadline: Deadline = None
    execution_deadline: Deadline = None

    @field_validator("source", mode="before")
    @classmethod
    def normalize_source(cls, value: object) -> object:
        value = _trim_required(value, "source")
        if isinstance(value, str):
            value = value.lower()
            if not SOURCE_PATTERN.fullmatch(value):
                raise ValueError("source has an invalid ASCII code format.")
        return value

    @field_validator("external_id", "title", mode="before")
    @classmethod
    def trim_required_text(cls, value: object, info) -> object:
        return _trim_required(value, info.field_name)

    @field_validator(
        "procurement_number",
        "customer",
        "procurement_type",
        mode="before",
    )
    @classmethod
    def trim_optional_text(cls, value: object, info) -> object:
        return _trim_optional(value, info.field_name)

    @field_validator("procurement_type")
    @classmethod
    def validate_procurement_type(cls, value: str | None) -> str | None:
        if value is not None and not NORMALIZED_CODE_PATTERN.fullmatch(value):
            raise ValueError("procurement_type must be a normalized ASCII code.")
        return value

    @field_validator("source_url", mode="before")
    @classmethod
    def normalize_source_url(cls, value: object) -> object:
        value = _trim_optional(value, "source_url")
        if isinstance(value, str):
            return str(HTTP_URL_ADAPTER.validate_python(value))
        return value

    @field_validator("region_code", mode="before")
    @classmethod
    def normalize_region_code(cls, value: object) -> object:
        if value is None:
            return None
        return _normalize_reference_code(value, "region_code")

    @field_validator("unit", mode="before")
    @classmethod
    def normalize_unit(cls, value: object) -> object:
        value = _trim_optional(value, "unit")
        if isinstance(value, str) and not NORMALIZED_CODE_PATTERN.fullmatch(value):
            raise ValueError("unit must be a normalized ASCII code.")
        return value

    @field_validator("price_amount", "quantity", mode="before")
    @classmethod
    def require_decimal_strings(cls, value: object) -> object:
        return _require_decimal_string(value)

    @field_validator("okpd2_codes", mode="after")
    @classmethod
    def validate_okpd2_codes(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized: list[str] = []
        for code in value:
            code = code.strip()
            if not OKPD2_PATTERN.fullmatch(code):
                raise ValueError(f"Invalid OKPD2 code: {code!r}.")
            normalized.append(code)
        if len(normalized) != len(set(normalized)):
            raise ValueError("Duplicate OKPD2 codes are not allowed.")
        return normalized

    @field_validator("product_type_codes", mode="after")
    @classmethod
    def validate_product_type_codes(
        cls,
        value: list[str] | None,
    ) -> list[str] | None:
        if value is None:
            return None
        normalized = [
            _normalize_reference_code(code, "product_type_code") for code in value
        ]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Duplicate product type codes are not allowed.")
        return normalized

    @field_validator("application_deadline", "execution_deadline")
    @classmethod
    def normalize_deadline(cls, value: Deadline) -> Deadline:
        return _normalize_deadline(value)

    @model_validator(mode="after")
    def validate_business_invariants(self) -> Self:
        if self.price_amount is not None and self.price_currency is None:
            raise ValueError("price_amount requires price_currency.")
        if self.quantity is not None and self.unit is None:
            raise ValueError("quantity requires unit.")

        signals = (
            self.okpd2_codes,
            self.product_type_codes,
            self.material_requirements,
            self.technology_requirements,
            self.equipment_requirements,
            self.dimensional_mass_requirements,
            self.quality_requirements,
            self.required_certificates,
        )
        if not any(signal for signal in signals):
            raise ValueError("At least one structured signal must be nonempty.")

        self._reject_duplicate_targets(
            self.material_requirements,
            lambda item: (
                ("material", item.material_id)
                if item.material_id is not None
                else ("group", item.material_group_code)
            ),
            "material requirement",
        )
        self._reject_duplicate_targets(
            self.technology_requirements,
            lambda item: item.technology_code,
            "technology requirement",
        )
        self._reject_duplicate_targets(
            self.equipment_requirements,
            lambda item: item.equipment_type_code,
            "equipment requirement",
        )
        self._reject_duplicate_targets(
            self.required_certificates,
            lambda item: item.certificate_type_code,
            "certificate requirement",
        )
        return self

    @staticmethod
    def _reject_duplicate_targets(
        items: list[Any] | None,
        key,
        label: str,
    ) -> None:
        if items is None:
            return
        targets = [key(item) for item in items]
        if len(targets) != len(set(targets)):
            raise ValueError(f"Duplicate {label} targets are not allowed.")


class PreparedOpportunityDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunities: list[PreparedOpportunityInput] = Field(min_length=1)


class ProcurementOpportunityIngestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    received_rows: int = Field(ge=1)
    unique_identities: int = Field(ge=1)
    created: int = Field(ge=0)
    updated: int = Field(ge=0)
    unchanged: int = Field(ge=0)
    duplicate_rows: int = Field(ge=0)


class ProcurementOpportunityRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    source: str
    external_id: str
    procurement_number: str | None
    title: str
    customer: str | None
    source_url: str | None
    status: ProcurementOpportunityStatus
    procurement_type: str | None
    okpd2_codes: list[str] | None
    product_type_codes: list[str] | None
    price_amount: Decimal | None
    price_currency: str | None
    region_code: str | None
    quantity: Decimal | None
    unit: str | None
    application_deadline: Deadline
    execution_deadline: Deadline
    material_requirements: list[MaterialRequirementInput] | None
    technology_requirements: list[TechnologyRequirementInput] | None
    equipment_requirements: list[EquipmentRequirementInput] | None
    dimensional_mass_requirements: list[DimensionalMassRequirementInput] | None
    quality_requirements: list[QualityRequirementInput] | None
    required_certificates: list[CertificateRequirementInput] | None

    @classmethod
    def from_canonical(
        cls,
        opportunity_id: int,
        record: PreparedOpportunityInput,
    ) -> Self:
        values = {
            name: getattr(record, name)
            for name in PreparedOpportunityInput.model_fields
        }
        return cls(id=opportunity_id, **values)


def canonicalize_opportunity(
    record: PreparedOpportunityInput,
) -> PreparedOpportunityInput:
    """Return a deterministic, semantic ordering of every collection."""
    updates: dict[str, Any] = {
        "application_deadline": _normalize_deadline(record.application_deadline),
        "execution_deadline": _normalize_deadline(record.execution_deadline),
    }
    if record.okpd2_codes is not None:
        updates["okpd2_codes"] = sorted(record.okpd2_codes)
    if record.product_type_codes is not None:
        updates["product_type_codes"] = sorted(record.product_type_codes)
    if record.material_requirements is not None:
        updates["material_requirements"] = sorted(
            record.material_requirements,
            key=lambda item: (
                item.material_group_code,
                item.material_id if item.material_id is not None else -1,
            ),
        )
    if record.technology_requirements is not None:
        updates["technology_requirements"] = sorted(
            record.technology_requirements,
            key=lambda item: item.technology_code,
        )
    if record.equipment_requirements is not None:
        updates["equipment_requirements"] = sorted(
            record.equipment_requirements,
            key=lambda item: item.equipment_type_code,
        )
    if record.required_certificates is not None:
        updates["required_certificates"] = sorted(
            record.required_certificates,
            key=lambda item: item.certificate_type_code,
        )
    return record.model_copy(update=updates)


def _decimal_string(value: Decimal | None, places: int) -> str | None:
    if value is None:
        return None
    return f"{value:.{places}f}"


def _deadline_string(value: Deadline) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return value.isoformat()


def canonical_payload(record: PreparedOpportunityInput) -> dict[str, Any]:
    """Build the complete mutable payload with explicit nulls and fixed scales."""
    record = canonicalize_opportunity(record)

    materials = None
    if record.material_requirements is not None:
        materials = [
            {
                "material_group_code": item.material_group_code,
                "material_id": item.material_id,
                "requirement_strength": item.requirement_strength.value,
            }
            for item in record.material_requirements
        ]

    technologies = None
    if record.technology_requirements is not None:
        technologies = [
            {
                "technology_code": item.technology_code,
                "requirement_strength": item.requirement_strength.value,
            }
            for item in record.technology_requirements
        ]

    equipment = None
    if record.equipment_requirements is not None:
        equipment = [
            {
                "equipment_type_code": item.equipment_type_code,
                "cnc": item.cnc,
                "axes": item.axes,
                "working_zone_x_mm": _decimal_string(
                    item.working_zone_x_mm,
                    3,
                ),
                "working_zone_y_mm": _decimal_string(
                    item.working_zone_y_mm,
                    3,
                ),
                "working_zone_z_mm": _decimal_string(
                    item.working_zone_z_mm,
                    3,
                ),
                "diameter_mm": _decimal_string(item.diameter_mm, 3),
                "requirement_strength": item.requirement_strength.value,
            }
            for item in record.equipment_requirements
        ]

    dimensions = None
    if record.dimensional_mass_requirements is not None:
        dimensions = [
            {
                "length_mm": _decimal_string(item.length_mm, 3),
                "width_mm": _decimal_string(item.width_mm, 3),
                "height_mm": _decimal_string(item.height_mm, 3),
                "diameter_mm": _decimal_string(item.diameter_mm, 3),
                "mass_kg": _decimal_string(item.mass_kg, 3),
                "requirement_strength": item.requirement_strength.value,
            }
            for item in record.dimensional_mass_requirements
        ]

    quality = None
    if record.quality_requirements is not None:
        quality = [
            {
                "required_it_grade": item.required_it_grade,
                "maximum_ra_um": _decimal_string(item.maximum_ra_um, 4),
                "measuring_capability_required": (item.measuring_capability_required),
                "cmm_required": item.cmm_required,
                "requirement_strength": item.requirement_strength.value,
            }
            for item in record.quality_requirements
        ]

    certificates = None
    if record.required_certificates is not None:
        certificates = [
            {
                "certificate_type_code": item.certificate_type_code,
                "requirement_strength": item.requirement_strength.value,
                "required_by": (
                    item.required_by.isoformat()
                    if item.required_by is not None
                    else None
                ),
                "valid_through": (
                    item.valid_through.isoformat()
                    if item.valid_through is not None
                    else None
                ),
            }
            for item in record.required_certificates
        ]

    return {
        "procurement_number": record.procurement_number,
        "title": record.title,
        "customer": record.customer,
        "source_url": record.source_url,
        "status": record.status.value,
        "procurement_type": record.procurement_type,
        "okpd2_codes": record.okpd2_codes,
        "product_type_codes": record.product_type_codes,
        "price_amount": _decimal_string(record.price_amount, 2),
        "price_currency": record.price_currency,
        "region_code": record.region_code,
        "quantity": _decimal_string(record.quantity, 6),
        "unit": record.unit,
        "application_deadline": _deadline_string(record.application_deadline),
        "execution_deadline": _deadline_string(record.execution_deadline),
        "material_requirements": materials,
        "technology_requirements": technologies,
        "equipment_requirements": equipment,
        "dimensional_mass_requirements": dimensions,
        "quality_requirements": quality,
        "required_certificates": certificates,
    }


def canonical_payload_json(record: PreparedOpportunityInput) -> str:
    return json.dumps(
        canonical_payload(record),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
