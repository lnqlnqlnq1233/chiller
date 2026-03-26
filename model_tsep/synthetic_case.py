from __future__ import annotations

import math

from .schemas import (
    CaseConfig,
    ChillerConfig,
    PlantAuxConfig,
    ScenarioSet,
    StorageConfig,
    UncertaintyBudget,
)


def _daily_wave(hour: int, phase_shift: float = 0.0) -> float:
    return math.sin((hour - 6 + phase_shift) / 24.0 * 2.0 * math.pi)


def create_benchmark_case() -> CaseConfig:
    hours = list(range(24))

    wetbulb = [24.0 + 3.8 * max(0.0, _daily_wave(hour)) + 0.6 * _daily_wave(hour, phase_shift=3.0) for hour in hours]
    wetbulb_dev = [0.8 + 0.2 * max(0.0, _daily_wave(hour)) for hour in hours]

    tariff = []
    tariff_dev = []
    for hour in hours:
        if 0 <= hour <= 6:
            tariff.append(0.48)
            tariff_dev.append(0.05)
        elif 7 <= hour <= 11:
            tariff.append(0.78)
            tariff_dev.append(0.08)
        elif 12 <= hour <= 17:
            tariff.append(1.02)
            tariff_dev.append(0.12)
        elif 18 <= hour <= 21:
            tariff.append(1.22)
            tariff_dev.append(0.14)
        else:
            tariff.append(0.72)
            tariff_dev.append(0.07)

    load_components_nominal = {
        "base_internal": [690.0 + 35.0 * _daily_wave(hour, phase_shift=-1.0) for hour in hours],
        "ambient_sensitive": [120.0 + 95.0 * max(0.0, _daily_wave(hour)) for hour in hours],
        "process_variation": [85.0 + 30.0 * max(0.0, _daily_wave(hour, phase_shift=5.0)) for hour in hours],
    }
    load_components_deviation = {
        "base_internal": [18.0 for _ in hours],
        "ambient_sensitive": [22.0 + 18.0 * max(0.0, _daily_wave(hour)) for hour in hours],
        "process_variation": [14.0 + 6.0 * max(0.0, _daily_wave(hour, phase_shift=5.0)) for hour in hours],
    }

    chillers = [
        ChillerConfig(
            name="CH1",
            max_cooling_kw=460.0,
            min_plr=0.35,
            startup_cost=28.0,
            fixed_power_kw=24.0,
            segment_cooling_kw=[90.0, 110.0, 99.0],
            base_segment_cop=[6.35, 6.1, 5.55],
            wetbulb_sensitivity=0.015,
            capacity_wetbulb_derate=0.010,
        ),
        ChillerConfig(
            name="CH2",
            max_cooling_kw=450.0,
            min_plr=0.35,
            startup_cost=28.0,
            fixed_power_kw=24.0,
            segment_cooling_kw=[85.0, 110.0, 97.5],
            base_segment_cop=[6.25, 6.05, 5.5],
            wetbulb_sensitivity=0.015,
            capacity_wetbulb_derate=0.010,
        ),
        ChillerConfig(
            name="CH3",
            max_cooling_kw=390.0,
            min_plr=0.4,
            startup_cost=22.0,
            fixed_power_kw=20.0,
            segment_cooling_kw=[72.0, 96.0, 66.0],
            base_segment_cop=[5.9, 5.7, 5.2],
            wetbulb_sensitivity=0.017,
            capacity_wetbulb_derate=0.012,
        ),
        ChillerConfig(
            name="CH4_small",
            max_cooling_kw=190.0,
            min_plr=0.3,
            startup_cost=11.0,
            fixed_power_kw=8.0,
            segment_cooling_kw=[36.0, 46.0, 51.0],
            base_segment_cop=[5.75, 5.55, 5.15],
            wetbulb_sensitivity=0.018,
            capacity_wetbulb_derate=0.013,
        ),
    ]

    storage = StorageConfig(
        energy_capacity_kwh=900.0,
        charge_power_kw=260.0,
        discharge_power_kw=260.0,
        charge_efficiency=0.95,
        discharge_efficiency=0.95,
        initial_soc_kwh=450.0,
        throughput_cost_per_kwh=0.01,
    )

    plant_aux = PlantAuxConfig(
        chilled_pump_design_kw=120.0,
        condenser_pump_design_kw=105.0,
        tower_design_kw=78.0,
        chilled_flow_load_coeff=0.68,
        chilled_flow_active_coeff=0.08,
        condenser_flow_load_coeff=0.72,
        tower_load_coeff=0.62,
        tower_wetbulb_coeff=0.08,
        tower_reference_wetbulb_c=23.0,
    )

    scenario = ScenarioSet(
        horizon_hours=hours,
        load_components_nominal=load_components_nominal,
        load_components_deviation=load_components_deviation,
        tariff_nominal=tariff,
        tariff_deviation=tariff_dev,
        wetbulb_nominal_c=wetbulb,
        wetbulb_deviation_c=wetbulb_dev,
        budget=UncertaintyBudget(load_gamma=1.4, price_gamma=5.0),
    )

    return CaseConfig(
        name="benchmark_multi_chiller_24h",
        hours=hours,
        chillers=chillers,
        storage=storage,
        plant_aux=plant_aux,
        scenario=scenario,
        unmet_cooling_penalty_per_kwh=100.0,
        default_solver="highs",
    )
