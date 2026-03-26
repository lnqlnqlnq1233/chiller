from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(slots=True)
class ChillerConfig:
    name: str
    max_cooling_kw: float
    min_plr: float
    startup_cost: float
    fixed_power_kw: float
    segment_cooling_kw: list[float]
    base_segment_cop: list[float]
    wetbulb_sensitivity: float
    capacity_wetbulb_derate: float


@dataclass(slots=True)
class StorageConfig:
    energy_capacity_kwh: float
    charge_power_kw: float
    discharge_power_kw: float
    charge_efficiency: float
    discharge_efficiency: float
    initial_soc_kwh: float
    throughput_cost_per_kwh: float


@dataclass(slots=True)
class PlantAuxConfig:
    chilled_pump_design_kw: float
    condenser_pump_design_kw: float
    tower_design_kw: float
    chilled_flow_load_coeff: float
    chilled_flow_active_coeff: float
    condenser_flow_load_coeff: float
    tower_load_coeff: float
    tower_wetbulb_coeff: float
    tower_reference_wetbulb_c: float


@dataclass(slots=True)
class UncertaintyBudget:
    load_gamma: float
    price_gamma: float


@dataclass(slots=True)
class ScenarioSet:
    horizon_hours: list[int]
    load_components_nominal: dict[str, list[float]]
    load_components_deviation: dict[str, list[float]]
    tariff_nominal: list[float]
    tariff_deviation: list[float]
    wetbulb_nominal_c: list[float]
    wetbulb_deviation_c: list[float]
    budget: UncertaintyBudget

    @property
    def total_nominal_load(self) -> list[float]:
        totals: list[float] = []
        component_names = list(self.load_components_nominal.keys())
        for idx in range(len(self.horizon_hours)):
            totals.append(sum(self.load_components_nominal[name][idx] for name in component_names))
        return totals

    @property
    def max_possible_load(self) -> list[float]:
        totals: list[float] = []
        component_names = list(self.load_components_nominal.keys())
        for idx in range(len(self.horizon_hours)):
            totals.append(
                sum(
                    self.load_components_nominal[name][idx] + self.load_components_deviation[name][idx]
                    for name in component_names
                )
            )
        return totals


@dataclass(slots=True)
class CaseConfig:
    name: str
    hours: list[int]
    chillers: list[ChillerConfig]
    storage: StorageConfig
    plant_aux: PlantAuxConfig
    scenario: ScenarioSet
    unmet_cooling_penalty_per_kwh: float = 50.0
    default_solver: str = "highs"

    @property
    def total_installed_cooling_kw(self) -> float:
        return sum(chiller.max_cooling_kw for chiller in self.chillers)


@dataclass(slots=True)
class ResultBundle:
    case_name: str
    method: str
    solver_name: str
    solver_status: str
    objective_value: float
    objective_breakdown: dict[str, float]
    dispatch: pd.DataFrame
    kpis: dict[str, float]
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_metadata(self, **kwargs: Any) -> "ResultBundle":
        metadata = dict(self.metadata)
        metadata.update(kwargs)
        return ResultBundle(
            case_name=self.case_name,
            method=self.method,
            solver_name=self.solver_name,
            solver_status=self.solver_status,
            objective_value=self.objective_value,
            objective_breakdown=self.objective_breakdown,
            dispatch=self.dispatch,
            kpis=self.kpis,
            metadata=metadata,
        )
