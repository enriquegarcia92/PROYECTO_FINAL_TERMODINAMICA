from vle_poc.repository import DataRepository
from vle_poc.validation import InputValidationError


def test_demo_database_has_binary_and_multicomponent_systems() -> None:
    systems = DataRepository().all_systems()
    sizes = {len(system.components) for system in systems}
    assert 2 in sizes
    assert any(size >= 3 for size in sizes)


def test_all_systems_support_three_activity_models() -> None:
    for system in DataRepository().all_systems():
        assert set(system.available_models) == {"Wilson", "Margules", "Van Laar"}


def test_component_catalog_is_loaded() -> None:
    components = DataRepository().all_components()
    ids = {component.id for component in components}
    assert {"cyclohexane", "n_heptane", "ethanol", "toluene"}.issubset(ids)


def test_dynamic_system_can_be_built_with_two_three_and_five_components() -> None:
    repository = DataRepository()
    binary = repository.build_system(("cyclohexane", "n_heptane"))
    ternary = repository.build_system(("acetone", "methanol", "benzene"))
    five = repository.build_system(("cyclohexane", "n_heptane", "ethanol", "toluene", "benzene"))
    assert len(binary.components) == 2
    assert len(ternary.components) == 3
    assert len(five.components) == 5


def test_dynamic_system_rejects_one_repeated_or_more_than_five_components() -> None:
    repository = DataRepository()
    for component_ids in [
        ("cyclohexane",),
        ("cyclohexane", "cyclohexane"),
        ("cyclohexane", "n_heptane", "ethanol", "toluene", "benzene", "methanol"),
    ]:
        try:
            repository.build_system(component_ids)
        except InputValidationError:
            pass
        else:
            raise AssertionError(f"Se esperaba rechazo para {component_ids}")
