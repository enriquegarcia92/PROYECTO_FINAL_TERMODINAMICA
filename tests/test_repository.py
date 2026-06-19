from vle_poc.repository import DataRepository


def test_demo_database_has_binary_and_multicomponent_systems() -> None:
    systems = DataRepository().all_systems()
    sizes = {len(system.components) for system in systems}
    assert 2 in sizes
    assert any(size >= 3 for size in sizes)


def test_all_systems_support_three_activity_models() -> None:
    for system in DataRepository().all_systems():
        assert set(system.available_models) == {"Wilson", "Margules", "Van Laar"}
