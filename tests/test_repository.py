from vle_poc.repository import DataRepository


def test_beta_database_has_documented_binary_systems() -> None:
    systems = DataRepository().all_systems()
    sizes = {len(system.components) for system in systems}
    assert sizes == {2, 3}
    assert len(systems) >= 10


def test_systems_declare_only_available_models() -> None:
    repository = DataRepository()
    assert repository.get("benzene_n_hexane").available_models == ("Wilson",)
    assert repository.get("cyclohexane_n_heptane").available_models == ("Wilson", "Margules", "Van Laar")
    assert repository.get("acetone_methanol").available_models == ("Margules",)


def test_component_catalog_is_loaded() -> None:
    components = DataRepository().all_components()
    ids = {component.id for component in components}
    assert {
        "benzene",
        "carbon_tetrachloride",
        "cyclohexane",
        "n_heptane",
        "n_hexane",
        "water",
        "n_pentane",
        "methane",
        "n_butane",
        "nitrogen",
    }.issubset(ids)


def test_problem_1427_is_available_only_for_wilson() -> None:
    system = DataRepository().get("water_n_pentane_n_heptane_1427")
    assert tuple(component.id for component in system.components) == ("water", "n_pentane", "n_heptane")
    assert system.available_models == ("Wilson",)
    assert "VLLE inmiscible" in system.kind


def test_acetone_methanol_water_ternary_is_available_only_for_wilson() -> None:
    system = DataRepository().get("acetone_methanol_water_1220_1222")
    assert tuple(component.id for component in system.components) == ("acetone", "methanol", "water")
    assert system.available_models == ("Wilson",)
    assert "Tabla 12.5" in system.description


def test_chapter_14_eos_systems_are_available_only_for_their_eos() -> None:
    repository = DataRepository()

    methane_butane = repository.get("methane_n_butane_1402")
    assert tuple(component.id for component in methane_butane.components) == ("methane", "n_butane")
    assert methane_butane.available_models == ("Soave-Redlich-Kwong",)
    assert "Ejemplo 14.2" in methane_butane.description

    nitrogen_methane = repository.get("nitrogen_methane_1401")
    assert tuple(component.id for component in nitrogen_methane.components) == ("nitrogen", "methane")
    assert nitrogen_methane.available_models == ("Redlich-Kwong",)
    assert "Ejemplo 14.1" in nitrogen_methane.description


def test_wilson_1454_parameters_are_loaded_for_fixed_systems() -> None:
    repository = DataRepository()
    system = repository.get("benzene_carbon_tetrachloride")
    pairs = system.binary_parameters["Wilson"]["pairs"]
    assert pairs["benzene|carbon_tetrachloride"]["value"] == 1.0372
    assert pairs["carbon_tetrachloride|benzene"]["value"] == 0.8637


def test_wilson_125_parameters_are_loaded_for_acetone_methanol_water() -> None:
    repository = DataRepository()
    system = repository.get("acetone_methanol_water_1220_1222")
    pairs = system.binary_parameters["Wilson"]["pairs"]
    expected = {
        "acetone|methanol": 583.11,
        "methanol|acetone": 161.88,
        "acetone|water": 1448.01,
        "water|acetone": 291.27,
        "methanol|water": 469.55,
        "water|methanol": 107.38,
    }
    for pair_key, value in expected.items():
        assert pairs[pair_key]["type"] == "energy_difference"
        assert pairs[pair_key]["units"] == "cal/mol"
        assert pairs[pair_key]["value"] == value
