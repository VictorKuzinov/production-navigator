from app.schemas import EquipmentCreate, EquipmentUpdate


def test_equipment_create_applies_documented_defaults() -> None:
    equipment = EquipmentCreate(
        equipment_type_code="TURNING",
        model_name="Test lathe",
    )

    assert equipment.cnc is False
    assert equipment.quantity == 1
    assert equipment.axes is None
    assert equipment.model_name == "Test lathe"


def test_equipment_update_can_clear_model_name_without_touching_other_fields() -> None:
    update = EquipmentUpdate(model_name=None)

    assert update.model_fields_set == {"model_name"}
    assert update.model_dump(exclude_unset=True) == {"model_name": None}
