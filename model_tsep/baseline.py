from __future__ import annotations

from collections import defaultdict

import pandas as pd

from .schemas import CaseConfig, ResultBundle


def run_rule_based_baseline(case: CaseConfig) -> ResultBundle:
    scenario = case.scenario
    storage = case.storage
    aux = case.plant_aux

    records: list[dict[str, float | int | str]] = []
    objective_breakdown = defaultdict(float)
    soc = storage.initial_soc_kwh
    previous_on = {chiller.name: 0 for chiller in case.chillers}

    for t in case.hours:
        load = scenario.total_nominal_load[t]
        price = scenario.tariff_nominal[t]
        wetbulb = scenario.wetbulb_nominal_c[t]
        target_charge = min(storage.charge_power_kw, max(0.0, storage.energy_capacity_kwh - soc)) if price <= 0.6 else 0.0
        target_discharge = min(storage.discharge_power_kw, soc) if price >= 1.05 else 0.0
        net_required = max(0.0, load + target_charge - target_discharge)

        ranking = []
        for chiller in case.chillers:
            avg_cop = sum(chiller.base_segment_cop) / len(chiller.base_segment_cop)
            penalty = 1.0 + chiller.wetbulb_sensitivity * max(0.0, wetbulb - 23.0)
            ranking.append((penalty / avg_cop, chiller))
        ranking.sort(key=lambda item: item[0])

        remaining = net_required
        total_cooling = 0.0
        chiller_power = 0.0
        active_count = 0
        chiller_dispatch: dict[str, float] = {}

        for _, chiller in ranking:
            min_output = chiller.max_cooling_kw * chiller.min_plr
            if remaining <= 1e-6 and price > 0.6:
                chiller_dispatch[chiller.name] = 0.0
                continue
            if remaining > chiller.max_cooling_kw:
                q = chiller.max_cooling_kw
            elif remaining > 0.0:
                q = max(min_output, remaining)
            else:
                q = 0.0
            if q > 0.0:
                active_count += 1
                total_cooling += q
                remaining = max(0.0, remaining - q)
                marginal_power = q / (sum(chiller.base_segment_cop) / len(chiller.base_segment_cop))
                chiller_power += chiller.fixed_power_kw + marginal_power * (1.0 + chiller.wetbulb_sensitivity * max(0.0, wetbulb - 23.0))
                if previous_on[chiller.name] == 0:
                    objective_breakdown["startup_cost"] += chiller.startup_cost
                previous_on[chiller.name] = 1
            else:
                previous_on[chiller.name] = 0
            chiller_dispatch[chiller.name] = q

        charge = min(target_charge, max(0.0, total_cooling - load))
        discharge = min(target_discharge, load)
        soc = min(storage.energy_capacity_kwh, max(0.0, soc + storage.charge_efficiency * charge - discharge / storage.discharge_efficiency))

        actual_supply = total_cooling + discharge - charge
        unmet = max(0.0, load - actual_supply)
        flow_chw = min(1.0, aux.chilled_flow_load_coeff * (total_cooling / case.total_installed_cooling_kw) + aux.chilled_flow_active_coeff * (active_count / len(case.chillers)))
        flow_cw = min(1.0, aux.condenser_flow_load_coeff * (total_cooling / case.total_installed_cooling_kw))
        tower_level = min(1.0, aux.tower_load_coeff * (total_cooling / case.total_installed_cooling_kw) + aux.tower_wetbulb_coeff * max(0.0, wetbulb - aux.tower_reference_wetbulb_c) / 10.0)
        aux_power = aux.chilled_pump_design_kw * flow_chw + aux.condenser_pump_design_kw * flow_cw + aux.tower_design_kw * tower_level
        grid_power = chiller_power + aux_power

        objective_breakdown["energy_cost"] += price * grid_power
        objective_breakdown["storage_cost"] += storage.throughput_cost_per_kwh * (charge + discharge)
        objective_breakdown["unmet_penalty"] += case.unmet_cooling_penalty_per_kwh * unmet

        row = {
            "hour": t,
            "load_kw": load,
            "grid_power_kw": grid_power,
            "cooling_supply_kw": actual_supply,
            "chiller_cooling_kw": total_cooling,
            "charge_kw": charge,
            "discharge_kw": discharge,
            "soc_kwh": soc,
            "unserved_kw": unmet,
            "flow_chw": flow_chw,
            "flow_cw": flow_cw,
            "tower_level": tower_level,
            "active_chillers": active_count,
            "tariff": price,
        }
        for name, value in chiller_dispatch.items():
            row[f"{name}_cooling_kw"] = value
            row[f"{name}_on"] = 1 if value > 1e-6 else 0
        records.append(row)

    dispatch = pd.DataFrame(records)
    total_cost = sum(objective_breakdown.values())
    total_power = dispatch["grid_power_kw"].sum()
    return ResultBundle(
        case_name=case.name,
        method="rule_based",
        solver_name="heuristic",
        solver_status="ok",
        objective_value=total_cost,
        objective_breakdown=dict(objective_breakdown),
        dispatch=dispatch,
        kpis={
            "total_cost": total_cost,
            "energy_cost": objective_breakdown["energy_cost"],
            "total_cooling_served_kwh": dispatch["cooling_supply_kw"].sum(),
            "total_unserved_kwh": dispatch["unserved_kw"].sum(),
            "peak_grid_power_kw": dispatch["grid_power_kw"].max(),
            "avg_cop": dispatch["cooling_supply_kw"].sum() / total_power if total_power > 0 else 0.0,
        },
        metadata={
            "solver_name": "heuristic",
            "robust_load": False,
            "robust_price": False,
            "robust_wetbulb": False,
            "storage_enabled": True,
            "pump_tower_enabled": True,
            "identical_chillers": False,
            "load_gamma": 0.0,
            "price_gamma": 0.0,
        },
    )
