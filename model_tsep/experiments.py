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


def _out_of_sample_metrics(bundle: ResultBundle, case: CaseConfig, samples: int = 24, seed: int = 7) -> dict[str, float]:
    rng = random.Random(seed)
    dispatch = bundle.dispatch
    scenario = case.scenario
    shortage = []
    realized_costs = []
    correlated_shortage = []
    for _ in range(samples):
        sample_shortage = 0.0
        sample_cost = 0.0
        corr_shortage = 0.0
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
            planned_supply = float(dispatch.loc[dispatch["hour"] == hour, "cooling_supply_kw"].iloc[0])
            planned_power = float(dispatch.loc[dispatch["hour"] == hour, "grid_power_kw"].iloc[0])
            sample_shortage += max(0.0, realized_load - planned_supply)
            corr_shortage += max(0.0, correlated_load - planned_supply)
            sample_cost += realized_tariff * planned_power
        shortage.append(sample_shortage)
        realized_costs.append(sample_cost)
        correlated_shortage.append(corr_shortage)
    shortage_series = pd.Series(shortage)
    cost_series = pd.Series(realized_costs)
    corr_series = pd.Series(correlated_shortage)
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
        options=ModelOptions(robust_load=True, robust_price=True, storage_enabled=True, pump_tower_enabled=True, identical_chillers=True),
    )
    bundle.kpis.update({"identical_chillers": 1})
    bundle.kpis.update(_out_of_sample_metrics(bundle, case))
    bundles.append(bundle)

    bundle = solve_case(
        case,
        method="no_pump_tower",
        options=ModelOptions(robust_load=True, robust_price=True, storage_enabled=True, pump_tower_enabled=False),
    )
    bundle.kpis.update({"pump_tower_enabled": 0})
    bundle.kpis.update(_out_of_sample_metrics(bundle, case))
    bundles.append(bundle)

    for bundle in bundles:
        export_result_bundle(bundle, output_path)
    export_comparison_table(bundles, output_path / "ablation_summary.csv")
    return bundles
