"""Carga catálogo de sustancias, plantillas y construye sistemas dinámicos."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .domain import MAX_COMPONENTS, MIN_COMPONENTS, AntoineParameters, Component, SystemDefinition
from .paths import resource_path
from .validation import InputValidationError


class DataRepository:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or resource_path("datos/base_datos_VLE.json")
        self._components: dict[str, Component] = {}
        self._systems: dict[str, SystemDefinition] = {}
        self._binary_parameters: dict[str, dict[str, Any]] = {}
        self._load()

    def _parse_component(self, raw: dict[str, Any]) -> Component:
        payload = dict(raw)
        antoine = payload.get("antoine")
        if antoine is not None:
            payload["antoine"] = AntoineParameters(**antoine)
        return Component(**payload)

    def _load(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(f"No se encontró la base de datos: {self.path}")
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self._binary_parameters = raw.get("binary_parameters", {})

        if "components" in raw:
            for component_raw in raw.get("components", []):
                component = self._parse_component(component_raw)
                if component.id in self._components:
                    raise ValueError(f"Componente duplicado: {component.id}")
                self._components[component.id] = component
            for template in raw.get("templates", []):
                system = self.build_system(
                    tuple(template["component_ids"]),
                    system_id=template["id"],
                    name=template["name"],
                    description=template["description"],
                    kind=template["kind"],
                    validate_count=False,
                )
                self._systems[system.id] = system
        else:
            # Compatibilidad con la estructura 0.2: sistemas con componentes embebidos.
            for item in raw.get("systems", []):
                components = tuple(self._parse_component(component) for component in item["components"])
                for component in components:
                    self._components.setdefault(component.id, component)
                system = SystemDefinition(
                    id=item["id"],
                    name=item["name"],
                    description=item["description"],
                    components=components,
                    available_models=tuple(item["available_models"]),
                    kind=item["kind"],
                    binary_parameters=item.get("binary_parameters", {}),
                )
                self._systems[system.id] = system

        if not self._components:
            raise ValueError("La base de datos no contiene sustancias.")
        if not self._systems:
            raise ValueError("La base de datos no contiene plantillas de sistemas.")

    def all_components(self) -> tuple[Component, ...]:
        return tuple(sorted(self._components.values(), key=lambda component: component.name))

    def get_component(self, component_id: str) -> Component:
        try:
            return self._components[component_id]
        except KeyError as exc:
            raise ValueError(f"Sustancia desconocida: {component_id}") from exc

    def all_systems(self) -> tuple[SystemDefinition, ...]:
        return tuple(self._systems.values())

    def get(self, system_id: str) -> SystemDefinition:
        try:
            return self._systems[system_id]
        except KeyError as exc:
            raise ValueError(f"Sistema desconocido: {system_id}") from exc

    def build_system(
        self,
        component_ids: tuple[str, ...],
        *,
        system_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        kind: str = "Dinámico",
        validate_count: bool = True,
    ) -> SystemDefinition:
        if len(set(component_ids)) != len(component_ids):
            raise InputValidationError("No se permiten sustancias repetidas en el sistema.")
        if validate_count and len(component_ids) < MIN_COMPONENTS:
            raise InputValidationError("Seleccione al menos 2 sustancias para ejecutar un cálculo VLE.")
        if len(component_ids) > MAX_COMPONENTS:
            raise InputValidationError(f"El máximo permitido es {MAX_COMPONENTS} sustancias.")

        components = tuple(self.get_component(component_id) for component_id in component_ids)
        system_name = name or " / ".join(component.name for component in components)
        return SystemDefinition(
            id=system_id or "dynamic__" + "__".join(component_ids),
            name=system_name,
            description=description or "Sistema construido desde el catálogo de sustancias.",
            components=components,
            available_models=("Wilson", "Margules", "Van Laar"),
            kind=kind,
            binary_parameters=self._parameters_for(component_ids),
        )

    def _parameters_for(self, component_ids: tuple[str, ...]) -> dict[str, Any]:
        selected: dict[str, Any] = {}
        for model, parameters in self._binary_parameters.items():
            pairs: dict[str, float] = {}
            sources: set[str] = set()
            parameter_type = ""
            for first in component_ids:
                for second in component_ids:
                    if first == second:
                        continue
                    key = f"{first}|{second}"
                    if key in parameters:
                        item = parameters[key]
                        pairs[key] = float(item["value"])
                        parameter_type = item.get("type", parameter_type)
                        if item.get("source"):
                            sources.add(item["source"])
            if pairs:
                selected[model] = {
                    "type": parameter_type,
                    "source": " | ".join(sorted(sources)),
                    "pairs": pairs,
                }
        return selected
