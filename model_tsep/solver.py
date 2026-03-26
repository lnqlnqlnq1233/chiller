from __future__ import annotations

import time
from typing import Any

import pandas as pd
import pyomo.environ as pyo

from .model_builder import ModelOptions, build_model
from .schemas import CaseConfig, ResultBundle, ScenarioSet


def _extract_results(model: pyo.ConcreteModel, case: CaseConfig, method: str, solver_name: str, results: Any) -> ResultBundle:
    rows: list[dict[str, float | int | str]] = []
    chiller_names = [ch.name for ch in case.chillers]
    for t in case.hours:
        row = {
            "hour": t,
            "load_kw": pyo.value(model.nominal_load[t]),
            "grid_power_kw": pyo.value(model.grid_power[t]),
            "cooling_supply_kw": pyo.value(model.total_supply[t]),
            "chiller_cooling_kw": pyo.value(model.total_cooling_from_chillers[t]),
            "charge_kw": pyo.value(model.charge[t]),
            "discharge_kw": pyo.value(model.discharge[t]),
            "soc_kwh": pyo.value(model.soc[t]),
            "unserved_kw": pyo.value(model.unserved[t]),
            "flow_chw": pyo.value(model.flow_chw[t]),
            "flow_cw": pyo.value(model.flow_cw[t]),
            "tower_level": pyo.value(model.tower_level[t]),
            "active_chillers": sum(round(pyo.value(model.on[c, t])) for c in model.C),
            "tariff": pyo.value(model.tariff[t]),
        }
        for c in chiller_names:
            row[f"{c}_cooling_kw"] = pyo.value(model.q_total[c, t])
            row[f"{c}_power_kw"] = pyo.value(model.chiller_power[c, t])
            row[f"{c}_on"] = round(pyo.value(model.on[c, t]))
        rows.append(row)
    dispatch = pd.DataFrame(rows)
    total_served = dispatch["cooling_supply_kw"].sum()
    total_power = dispatch["grid_power_kw"].sum()
    objective_breakdown = {
        "energy_cost": pyo.value(model.energy_cost_expr),
        "startup_cost": pyo.value(model.startup_cost_expr),
        "storage_cost": pyo.value(model.storage_cost_expr),
        "unmet_penalty": pyo.value(model.unmet_penalty_expr),
        "robust_price_cost": pyo.value(model.robust_price_cost_expr),
    }
    return ResultBundle(
        case_name=case.name,
        method=method,
        solver_name=solver_name,
        solver_status=str(results.solver.termination_condition),
        objective_value=pyo.value(model.total_cost),
        objective_breakdown=objective_breakdown,
        dispatch=dispatch,
        kpis={
            "total_cost": pyo.value(model.total_cost),
            "energy_cost": pyo.value(model.energy_cost_expr),
            "total_cooling_served_kwh": total_served,
            "total_unserved_kwh": dispatch["unserved_kw"].sum(),
            "peak_grid_power_kw": dispatch["grid_power_kw"].max(),
            "avg_cop": total_served / total_power if total_power > 0 else 0.0,
            "storage_cycles_equiv": dispatch["discharge_kw"].sum() / case.storage.energy_capacity_kwh if case.storage.energy_capacity_kwh > 0 else 0.0,
        },
    )


def solve_case(
    case: CaseConfig,
    method: str,
    solver_name: str | None = None,
    options: ModelOptions | None = None,
    scenario: ScenarioSet | None = None,
) -> ResultBundle:
    options = options or ModelOptions()
    solver_name = solver_name or case.default_solver
    model = build_model(case, options=options, scenario=scenario)
    solver = pyo.SolverFactory(solver_name)
    tic = time.perf_counter()
    results = solver.solve(model, tee=False)
    bundle = _extract_results(model, case, method=method, solver_name=solver_name, results=results)
    bundle.kpis["solve_time_sec"] = time.perf_counter() - tic
    bundle.metadata["solver_name"] = solver_name
    return bundle
