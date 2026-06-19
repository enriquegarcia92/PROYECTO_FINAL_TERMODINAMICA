"""Contratos de dominio compartidos por GUI, CLI y futuros solvers reales."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CalculationType(str, Enum):
    BUBL_P = "BUBL P"
    DEW_P = "DEW P"
    BUBL_T = "BUBL T"
    DEW_T = "DEW T"

    @property
    def known_phase(self) -> str:
        return "líquido" if self in {self.BUBL_P, self.BUBL_T} else "vapor"

    @property
    def fixed_variable(self) -> str:
        return "temperatura" if self in {self.BUBL_P, self.DEW_P} else "presión"


class ActivityModel(str, Enum):
    WILSON = "Wilson"
    MARGULES = "Margules"
    VAN_LAAR = "Van Laar"


class VaporModel(str, Enum):
    GAMMA_PHI = "Gamma-phi completo"
    COMPARE = "Comparar con phi = 1"


@dataclass(frozen=True)
class Component:
    id: str
    name: str
    formula: str
    tc_k: float
    pc_kpa: float
    omega: float


@dataclass(frozen=True)
class SystemDefinition:
    id: str
    name: str
    description: str
    components: tuple[Component, ...]
    available_models: tuple[str, ...]
    kind: str


@dataclass(frozen=True)
class CalculationRequest:
    calculation_type: CalculationType
    system_id: str
    activity_model: ActivityModel
    vapor_model: VaporModel
    fixed_value: float
    composition: tuple[float, ...]
    tolerance: float = 1e-4
    max_iterations: int = 100


@dataclass(frozen=True)
class CalculationResult:
    calculation_type: str
    system_name: str
    component_names: tuple[str, ...]
    temperature_k: float
    pressure_kpa: float
    x: tuple[float, ...]
    y: tuple[float, ...]
    gamma: tuple[float, ...]
    phi: tuple[float, ...]
    phi_sat: tuple[float, ...]
    poynting: tuple[float, ...]
    iterations: int
    converged: bool
    residuals: dict[str, float]
    warnings: tuple[str, ...]
    message: str
    activity_model: str
    vapor_model: str
    comparison_value: float | None = None
    comparison_label: str | None = None
    simulated: bool = True
    history: tuple[dict[str, float], ...] = field(default_factory=tuple)

    def assert_shape(self) -> None:
        """Comprueba que todos los vectores coincidan con los componentes."""
        size = len(self.component_names)
        for vector in (self.x, self.y, self.gamma, self.phi, self.phi_sat, self.poynting):
            if len(vector) != size:
                raise ValueError("Los vectores del resultado tienen dimensiones inconsistentes.")
