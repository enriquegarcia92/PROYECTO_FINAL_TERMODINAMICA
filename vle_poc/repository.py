"""Carga y valida el catálogo demostrativo de sistemas VLE."""

from __future__ import annotations

import json
from pathlib import Path

from .domain import AntoineParameters, Component, SystemDefinition
from .paths import resource_path


class DataRepository:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or resource_path("datos/base_datos_VLE.json")
        self._systems = self._load()

    def _load(self) -> dict[str, SystemDefinition]:
        if not self.path.exists():
            raise FileNotFoundError(f"No se encontró la base de datos: {self.path}")
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        systems: dict[str, SystemDefinition] = {}
        for item in raw.get("systems", []):
            parsed_components: list[Component] = []
            for component in item["components"]:
                payload = dict(component)
                antoine = payload.get("antoine")
                if antoine is not None:
                    payload["antoine"] = AntoineParameters(**antoine)
                parsed_components.append(Component(**payload))
            components = tuple(parsed_components)
            system = SystemDefinition(
                id=item["id"],
                name=item["name"],
                description=item["description"],
                components=components,
                available_models=tuple(item["available_models"]),
                kind=item["kind"],
                binary_parameters=item.get("binary_parameters", {}),
            )
            if system.id in systems:
                raise ValueError(f"Sistema duplicado: {system.id}")
            if len(system.components) < 2:
                raise ValueError(f"El sistema {system.id} debe tener al menos dos componentes.")
            systems[system.id] = system
        if not systems:
            raise ValueError("La base de datos no contiene sistemas.")
        return systems

    def all_systems(self) -> tuple[SystemDefinition, ...]:
        return tuple(self._systems.values())

    def get(self, system_id: str) -> SystemDefinition:
        try:
            return self._systems[system_id]
        except KeyError as exc:
            raise ValueError(f"Sistema desconocido: {system_id}") from exc
