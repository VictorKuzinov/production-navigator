class EnterpriseProfileNotFoundError(Exception):
    """Enterprise profile not found."""
    pass

class DuplicateInnError(Exception):
    """Duplicate inn found."""
    pass

class DuplicateOgrnError(Exception):
    """Duplicate ogrn found."""
    pass

class CompanySizeNotFoundError(Exception):
    """Company size not found."""
    pass

class RegionNotFoundError(Exception):
    """Region not found."""
    pass

class ProductionFacilityNotFoundError(Exception):
    """Production facility not found."""
    pass

class EquipmentNotFoundError(Exception):
    """Equipment not found."""
    pass

class EquipmentTypeNotFoundError(Exception):
    """Equipment type not found."""
    pass

class WarehouseNotFoundError(Exception):
    """Warehouse not found."""
    pass

class WarehouseTypeNotFoundError(Exception):
    """Warehouse type not found."""
    pass

class LiftingEquipmentNotFoundError(Exception):
    """Lifting equipment not found."""
    pass

class CraneTypeNotFoundError(Exception):
    """Crane type not found."""
    pass

class TransportNotFoundError(Exception):
    """Transport not found."""
    pass

class TransportTypeNotFoundError(Exception):
    """Transport type not found."""
    pass

class TransportScopeNotFoundError(Exception):
    """Transport scope not found."""
    pass

class TransportOwnershipTypeNotFoundError(Exception):
    """Transport ownership type not found."""
    pass


class MaterialNotFoundError(Exception):
    """Material not found."""
    pass


class MaterialGroupNotFoundError(Exception):
    """Material group not found."""
    pass


class DuplicateMaterialError(Exception):
    """Duplicate material found."""
    pass


class MaterialInUseError(Exception):
    """Material is referenced by material items."""
    pass


class MaterialItemNotFoundError(Exception):
    """Material item not found."""
    pass


class MaterialFormNotFoundError(Exception):
    """Material form not found."""
    pass


class DuplicateMaterialItemError(Exception):
    """Duplicate material item found."""
    pass


class MaterialItemInUseError(Exception):
    """Material item is referenced by products."""
    pass


class InvalidMaterialItemError(Exception):
    """Material item violates a cross-field domain invariant."""
    pass
