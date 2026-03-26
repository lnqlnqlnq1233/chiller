from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import random

import pandas as pd

from .baseline import run_rule_based_baseline
from .model_builder import ModelOptions
from .reporting import export_comparison_table, export_result_bundle
from .schemas import CaseConfig, ResultBundle, ScenarioSet
from .solver import solve_case
from .synthetic_case import create_benchmark_case


def _make_scenario(case: CaseConfig, *, load_gamma: float | None = None, price_gamma: float | None = None) -> ScenarioSet:
    scenario = deepcopy(case.scenario)
    if load_gamma is not None:
        scenario.budget.load_gamma = load_gamma
    if price_gamma is not None:
        scenario.budget.price_gamma = price_gamma
    return scenario


def _segment_power_slopes(chiller, wetbulb_c: float, identical_chillers: bool) -> list[float]:
    penalty_multiplier = 1.0 + chiller.wetbulb_sensitivity * max(0.0, wetbulb_c - 23.0)
    cop_vector = [6.0, 5.8, 5.35] if identical_chillers else chiller.base_segment_cop
    return [penalty_multiplier / cop for cop in cop_vector]


def _available_capacity(chiller, wetbulb_c: float) -> float:
    derate = chiller.capacity_wetbulb_derate * max(0.0, wetbulb_c - 23.0)
    return max(chiller.max_cooling_kw * 0.7, chiller.max_cooling_kw * (1.0 - derate))


def _segment_allocation(chiller, cooling_kw: float, on_flag: float) -> list[float]:
    if on_flag < 0.5 or cooling_kw <= 1e-9:
        return [0.0, 0.0, 0.0]
    min_output = chiller.max_cooling_kw * chiller.min_plr
    extra = max(0.0, cooling_kw - min_output)
    allocation: list[float] = []
    for width in chiller.segment_cooling_kw:
        take = min(width, extra)
        allocation.append(max(0.0, take))
        extra -= take
    while len(allocation) < 3:
        allocation.append(0.0)
    return allocation


def _realized_supply_and_power(bundle: ResultBundle, case: CaseConfig, dispatch_row: pd.Series, realized_wetbulb_c: float) -> tuple[float, float]:
    identical_chillers = bool(bundle.metadata.get("identical_chillers", False))
    pump_tower_enabled = bool(bundle.metadata.get("pump_tower_enabled", True))

    total_realized_cooling = 0.0
    total_chiller_power = 0.0
    for chiller in case.chillers:
        planned_cooling_kw = float(dispatch_row[f"{chiller.name}_cooling_kw"])
        on_flag = float(dispatch_row[f"{chiller.name}_on"])
        cooling_kw = min(planned_cooling_kw, _available_capacity(chiller, realized_wetbulb_c))
        total_realized_cooling += cooling_kw
        segments = _segment_allocation(chiller, cooling_kw, on_flag)
        slopes = _segment_power_slopes(chiller, realized_wetbulb_c, identical_chillers)
        total_chiller_power += chiller.fixed_power_kw * on_flag + sum(slope * seg for slope, seg in zip(slopes, segments))

    if not pump_tower_enabled:
        realized_supply = total_realized_cooling + float(dispatch_row["discharge_kw"]) - float(dispatch_row["charge_kw"])
        return realized_supply, total_chiller_power

    aux = case.plant_aux
    load_ratio = total_realized_cooling / case.total_installed_cooling_kw
    active_ratio = float(dispatch_row["active_chillers"]) / max(1, len(case.chillers))
    flow_chw = aux.chilled_flow_load_coeff * load_ratio + aux.chilled_flow_active_coeff * active_ratio
    flow_cw = aux.condenser_flow_load_coeff * load_ratio
    wetbulb_term = max(0.0, realized_wetbulb_c - aux.tower_reference_wetbulb_c) / 10.0
    tower_level = aux.tower_load_coeff * load_ratio + aux.tower_wetbulb_coeff * wetbulb_term

    realized_supply = total_realized_cooling + float(dispatch_row["discharge_kw"]) - float(dispatch_row["charge_kw"])
    realized_power = (
        total_chiller_power
        + aux.chilled_pump_design_kw * flow_chw
        + aux.condenser_pump_design_kw * flow_cw
        + aux.tower_design_kw * tower_level
    )
    return realized_supply, realized_power


def _out_of_sample_metrics(bundle: ResultBundle, case: CaseConfig, samples: int = 24, seed: int = 7) -> dict[str, float]:
    rng = random.Random(seed)
    dispatch = bundle.dispatch
    scenario = case.scenario
    shortage = []
    realized_costs = []
    correlated_shortage = []
    correlated_costs = []
    for _ in range(samples):
        sample_shortage = 0.0
        sample_cost = 0.0
        corr_shortage = 0.0
        corr_cost = 0.0
        weather_shock = rng.uniform(0.0, 1.0)
        for hour in case.hours:
            realized_load = 0.0
            correlated_load = 0.0
            for name in scenario.load_components_nominal:
                nominal = scenario.load_components_nominal[name][hour]
                dev = scenario.load_components_deviation[name][hour]
                realized_load += nominal + rng.uniform(0.0, dev)
                if name == "ambient_sensitive":
                    correlated_load += nominal + weather_shock * dev
                elif name == "process_variation":
                    correlated_load += nominal + (0.5 * weather_shock + 0.5 * rng.uniform(0.0, 1.0)) * dev
                else:
                    correlated_load += nominal + 0.25 * weather_shock * dev
            realized_tariff = scenario.tariff_nominal[hour] + rng.uniform(0.0, scenario.tariff_deviation[hour])
            realized_wetbulb = scenario.wetbulb_nominal_c[hour] + rng.uniform(0.0, scenario.wetbulb_deviation_c[hour])
            correlated_wetbulb = scenario.wetbulb_nominal_c[hour] + weather_shock * scenario.wetbulb_deviation_c[hour]
            dispatch_row = dispatch.loc[dispatch["hour"] == hour].iloc[0]
            realized_supply, realized_power = _realized_supply_and_power(bundle, case, dispatch_row, realized_wetbulb)
            correlated_supply, correlated_power = _realized_supply_and_power(bundle, case, dispatch_row, correlated_wetbulb)
            sample_shortage += max(0.0, realized_load - realized_supply)
            corr_shortage += max(0.0, correlated_load - correlated_supply)
            sample_cost += realized_tariff * realized_power
            corr_cost += realized_tariff * correlated_power
        shortage.append(sample_shortage)
        realized_costs.append(sample_cost)
        correlated_shortage.append(corr_shortage)
        correlated_costs.append(corr_cost)
    shortage_series = pd.Series(shortage)
    cost_series = pd.Series(realized_costs)
    corr_series = pd.Series(correlated_shortage)
    corr_cost_series = pd.Series(correlated_costs)
    return {
        "oos_mean_shortage_kwh": float(shortage_series.mean()),
        "oos_p90_shortage_kwh": float(shortage_series.quantile(0.9)),
        "oos_p95_shortage_kwh": float(shortage_series.quantile(0.95)),
        "oos_max_shortage_kwh": float(shortage_series.max()),
        "oos_violation_rate": float((shortage_series > 0.0).mean()),
        "oos_mean_energy_cost": float(cost_series.mean()),
        "oos_cost_std": float(cost_series.std(ddof=0)),
        "corr_oos_mean_shortage_kwh": float(corr_series.mean()),
        "corr_oos_p90_shortage_kwh": float(corr_series.quantile(0.9)),
        "corr_oos_mean_energy_cost": float(corr_cost_series.mean()),
    }


def run_benchmark(output_dir: str | Path = "outputs/benchmark") -> list[ResultBundle]:
    output_path = Path(output_dir)
    case = create_benchmark_case()
    results: list[ResultBundle] = []

    baseline = run_rule_based_baseline(case)
    baseline.kpis.update(_out_of_sample_metrics(baseline, case))
    results.append(baseline)

    deterministic = solve_case(
        case,
        method="deterministic_no_storage",
        options=ModelOptions(robust_load=False, robust_price=False, storage_enabled=False, pump_tower_enabled=True),
    )
    deterministic.kpis.update(_out_of_sample_metrics(deterministic, case))
    results.append(deterministic)

    deterministic_with_storage = solve_case(
        case,
        method="deterministic_with_storage",
        options=ModelOptions(robust_load=False, robust_price=False, storage_enabled=True, pump_tower_enabled=True),
    )
    deterministic_with_storage.kpis.update(_out_of_sample_metrics(deterministic_with_storage, case))
    results.append(deterministic_with_storage)

    robust_no_storage = solve_case(
        case,
        method="robust_no_storage",
        options=ModelOptions(robust_load=True, robust_price=True, storage_enabled=False, pump_tower_enabled=True),
    )
    robust_no_storage.kpis.update(_out_of_sample_metrics(robust_no_storage, case))
    results.append(robust_no_storage)

    robust_with_storage = solve_case(
        case,
        method="robust_with_storage",
        options=ModelOptions(robust_load=True, robust_price=True, storage_enabled=True, pump_tower_enabled=True),
    )
    robust_with_storage.kpis.update(_out_of_sample_metrics(robust_with_storage, case))
    results.append(robust_with_storage)

    robust_full_with_storage = solve_case(
        case,
        method="robust_full_with_storage",
        options=ModelOptions(robust_load=True, robust_price=True, robust_wetbulb=True, storage_enabled=True, pump_tower_enabled=True),
    )
    robust_full_with_storage.kpis.update(_out_of_sample_metrics(robust_full_with_storage, case))
    results.append(robust_full_with_storage)

    for bundle in results:
        export_result_bundle(bundle, output_path)
    export_comparison_table(results, output_path / "benchmark_summary.csv")
    return results


def run_ablations(output_dir: str | Path = "outputs/ablations") -> list[ResultBundle]:
    output_path = Path(output_dir)
    case = create_benchmark_case()
    bundles: list[ResultBundle] = []

    for gamma in [0.0, 0.7, 1.4, 2.2]:
        scenario = _make_scenario(case, load_gamma=gamma, price_gamma=5.0 if gamma > 0 else 0.0)
        bundle = solve_case(
            case,
            method=f"load_gamma_{str(gamma).replace('.', '_')}",
            options=ModelOptions(robust_load=gamma > 0, robust_price=gamma > 0, storage_enabled=True, pump_tower_enabled=True),
            scenario=scenario,
        )
        bundle.kpis.update({"ablation_gamma": gamma})
        bundle.kpis.update(_out_of_sample_metrics(bundle, case))
        bundles.append(bundle)

    small_storage_case = create_benchmark_case()
    small_storage_case.storage.energy_capacity_kwh = 450.0
    small_storage_case.storage.initial_soc_kwh = 225.0
    bundle = solve_case(
        small_storage_case,
        method="storage_small",
        options=ModelOptions(robust_load=True, robust_price=True, storage_enabled=True, pump_tower_enabled=True),
    )
    bundle.kpis.update({"storage_capacity_kwh": 450.0})
    bundle.kpis.update(_out_of_sample_metrics(bundle, small_storage_case))
    bundles.append(bundle)

    large_storage_case = create_benchmark_case()
    large_storage_case.storage.energy_capacity_kwh = 1400.0
    large_storage_case.storage.initial_soc_kwh = 700.0
    bundle = solve_case(
        large_storage_case,
        method="storage_large",
        options=ModelOptions(robust_load=True, robust_price=True, storage_enabled=True, pump_tower_enabled=True),
    )
    bundle.kpis.update({"storage_capacity_kwh": 1400.0})
    bundle.kpis.update(_out_of_sample_metrics(bundle, large_storage_case))
    bundles.append(bundle)

    bundle = solve_case(
        case,
        method="identical_chillers",
        options=ModelOptions(robust_load=True, robust_price=True, robust_wetbulb=True, storage_enabled=True, pump_tower_enabled=True, identical_chillers=True),
    )
    bundle.kpis.update({"identical_chillers": 1})
    bundle.kpis.update(_out_of_sample_metrics(bundle, case))
    bundles.append(bundle)

    bundle = solve_case(
        case,
        method="no_pump_tower",
        options=ModelOptions(robust_load=True, robust_price=True, robust_wetbulb=True, storage_enabled=True, pump_tower_enabled=False),
    )
    bundle.kpis.update({"pump_tower_enabled": 0})
    bundle.kpis.update(_out_of_sample_metrics(bundle, case))
    bundles.append(bundle)

    bundle = solve_case(
        case,
        method="no_weather_robustness",
        options=ModelOptions(robust_load=True, robust_price=True, robust_wetbulb=False, storage_enabled=True, pump_tower_enabled=True),
    )
    bundle.kpis.update({"weather_robust": 0})
    bundle.kpis.update(_out_of_sample_metrics(bundle, case))
    bundles.append(bundle)

    bundle = solve_case(
        case,
        method="with_weather_robustness",
        options=ModelOptions(robust_load=True, robust_price=True, robust_wetbulb=True, storage_enabled=True, pump_tower_enabled=True),
    )
    bundle.kpis.update({"weather_robust": 1})
    bundle.kpis.update(_out_of_sample_metrics(bundle, case))
    bundles.append(bundle)

    for bundle in bundles:
        export_result_bundle(bundle, output_path)
    export_comparison_table(bundles, output_path / "ablation_summary.csv")
    return bundles
