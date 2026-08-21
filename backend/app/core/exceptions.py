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