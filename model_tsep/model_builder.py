from __future__ import annotations

from dataclasses import dataclass

import pyomo.environ as pyo

from .schemas import CaseConfig, ScenarioSet


@dataclass(slots=True)
class ModelOptions:
    robust_load: bool = True
    robust_price: bool = True
    robust_wetbulb: bool = False
    storage_enabled: bool = True
    pump_tower_enabled: bool = True
    identical_chillers: bool = False


def _segment_power_slope(chiller, wetbulb_c: float, identical_chillers: bool) -> list[float]:
    penalty_multiplier = 1.0 + chiller.wetbulb_sensitivity * max(0.0, wetbulb_c - 23.0)
    if identical_chillers:
        cop_vector = [6.0, 5.8, 5.35]
    else:
        cop_vector = chiller.base_segment_cop
    return [penalty_multiplier / cop for cop in cop_vector]


def _available_capacity(chiller, wetbulb_c: float) -> float:
    derate = chiller.capacity_wetbulb_derate * max(0.0, wetbulb_c - 23.0)
    return max(chiller.max_cooling_kw * 0.7, chiller.max_cooling_kw * (1.0 - derate))


def build_model(case: CaseConfig, options: ModelOptions, scenario: ScenarioSet | None = None) -> pyo.ConcreteModel:
    scenario = scenario or case.scenario
    model = pyo.ConcreteModel(name=f"{case.name}_{'robust' if options.robust_load or options.robust_price else 'det'}")

    hours = case.hours
    chiller_names = [chiller.name for chiller in case.chillers]
    segment_names = [f"seg_{idx + 1}" for idx in range(3)]
    load_components = list(scenario.load_components_nominal.keys())

    chiller_map = {chiller.name: chiller for chiller in case.chillers}

    model.T = pyo.Set(initialize=hours, ordered=True)
    model.C = pyo.Set(initialize=chiller_names, ordered=True)
    model.S = pyo.Set(initialize=segment_names, ordered=True)
    model.L = pyo.Set(initialize=load_components, ordered=True)

    model.load_gamma = pyo.Param(initialize=scenario.budget.load_gamma if options.robust_load else 0.0)
    model.price_gamma = pyo.Param(initialize=scenario.budget.price_gamma if options.robust_price else 0.0)
    model.storage_enabled = pyo.Param(initialize=1 if options.storage_enabled else 0)
    model.total_installed_cooling_kw = pyo.Param(initialize=case.total_installed_cooling_kw)

    model.nominal_load = pyo.Param(model.T, initialize={t: scenario.total_nominal_load[t] for t in hours})
    model.tariff = pyo.Param(model.T, initialize={t: scenario.tariff_nominal[t] for t in hours})
    model.tariff_dev = pyo.Param(model.T, initialize={t: scenario.tariff_deviation[t] for t in hours})
    model.wetbulb_nominal = pyo.Param(model.T, initialize={t: scenario.wetbulb_nominal_c[t] for t in hours})
    model.wetbulb_dev = pyo.Param(model.T, initialize={t: scenario.wetbulb_deviation_c[t] for t in hours})

    model.load_dev_component = pyo.Param(
        model.L,
        model.T,
        initialize={(l, t): scenario.load_components_deviation[l][t] for l in load_components for t in hours},
    )

    model.chiller_max = pyo.Param(model.C, initialize={name: chiller_map[name].max_cooling_kw for name in chiller_names})
    model.chiller_available_max = pyo.Param(
        model.C,
        model.T,
        initialize={
            (
                name,
                t,
            ): _available_capacity(
                chiller_map[name],
                scenario.wetbulb_nominal_c[t] + (scenario.wetbulb_deviation_c[t] if options.robust_wetbulb else 0.0),
            )
            for name in chiller_names
            for t in hours
        },
    )
    model.chiller_min = pyo.Param(
        model.C,
        initialize={name: chiller_map[name].max_cooling_kw * chiller_map[name].min_plr for name in chiller_names},
    )
    model.startup_cost = pyo.Param(model.C, initialize={name: chiller_map[name].startup_cost for name in chiller_names})
    model.fixed_power = pyo.Param(model.C, initialize={name: chiller_map[name].fixed_power_kw for name in chiller_names})
    model.seg_width = pyo.Param(
        model.C,
        model.S,
        initialize={
            (name, segment_names[s_idx]): chiller_map[name].segment_cooling_kw[s_idx]
            for name in chiller_names
            for s_idx in range(3)
        },
    )
    model.seg_slope = pyo.Param(
        model.C,
        model.S,
        model.T,
        initialize={
            (
                name,
                segment_names[s_idx],
                t,
            ): _segment_power_slope(
                chiller_map[name],
                scenario.wetbulb_nominal_c[t] + (scenario.wetbulb_deviation_c[t] if options.robust_wetbulb else 0.0),
                options.identical_chillers,
            )[s_idx]
            for name in chiller_names
            for s_idx in range(3)
            for t in hours
        },
    )

    storage = case.storage
    aux = case.plant_aux
    model.storage_capacity = pyo.Param(initialize=storage.energy_capacity_kwh if options.storage_enabled else 0.0)
    model.charge_power_max = pyo.Param(initialize=storage.charge_power_kw if options.storage_enabled else 0.0)
    model.discharge_power_max = pyo.Param(initialize=storage.discharge_power_kw if options.storage_enabled else 0.0)
    model.charge_eff = pyo.Param(initialize=storage.charge_efficiency if options.storage_enabled else 1.0)
    model.discharge_eff = pyo.Param(initialize=storage.discharge_efficiency if options.storage_enabled else 1.0)
    model.initial_soc = pyo.Param(initialize=storage.initial_soc_kwh if options.storage_enabled else 0.0)
    model.storage_cost = pyo.Param(initialize=storage.throughput_cost_per_kwh if options.storage_enabled else 0.0)

    model.chwp_design = pyo.Param(initialize=aux.chilled_pump_design_kw if options.pump_tower_enabled else 0.0)
    model.cwp_design = pyo.Param(initialize=aux.condenser_pump_design_kw if options.pump_tower_enabled else 0.0)
    model.tower_design = pyo.Param(initialize=aux.tower_design_kw if options.pump_tower_enabled else 0.0)
    model.chwp_load_coeff = pyo.Param(initialize=aux.chilled_flow_load_coeff)
    model.chwp_active_coeff = pyo.Param(initialize=aux.chilled_flow_active_coeff)
    model.cwp_load_coeff = pyo.Param(initialize=aux.condenser_flow_load_coeff)
    model.tower_load_coeff = pyo.Param(initialize=aux.tower_load_coeff)
    model.tower_wb_coeff = pyo.Param(initialize=aux.tower_wetbulb_coeff)
    model.tower_ref_wb = pyo.Param(initialize=aux.tower_reference_wetbulb_c)

    model.q_extra = pyo.Var(model.C, model.T, model.S, domain=pyo.NonNegativeReals)
    model.q_total = pyo.Var(model.C, model.T, domain=pyo.NonNegativeReals)
    model.chiller_power = pyo.Var(model.C, model.T, domain=pyo.NonNegativeReals)
    model.on = pyo.Var(model.C, model.T, domain=pyo.Binary)
    model.start = pyo.Var(model.C, model.T, domain=pyo.Binary)
    model.stop = pyo.Var(model.C, model.T, domain=pyo.Binary)

    model.charge = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.discharge = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.soc = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.charge_on = pyo.Var(model.T, domain=pyo.Binary)
    model.discharge_on = pyo.Var(model.T, domain=pyo.Binary)

    model.flow_chw = pyo.Var(model.T, bounds=(0.0, 1.0))
    model.flow_cw = pyo.Var(model.T, bounds=(0.0, 1.0))
    model.tower_level = pyo.Var(model.T, bounds=(0.0, 1.0))
    model.chwp_power = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.cwp_power = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.tower_power = pyo.Var(model.T, domain=pyo.NonNegativeReals)

    model.grid_power = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.unserved = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.total_supply = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.total_cooling_from_chillers = pyo.Var(model.T, domain=pyo.NonNegativeReals)

    model.load_eta = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.load_rho = pyo.Var(model.L, model.T, domain=pyo.NonNegativeReals)
    model.price_theta = pyo.Var(domain=pyo.NonNegativeReals)
    model.price_psi = pyo.Var(model.T, domain=pyo.NonNegativeReals)

    def q_total_rule(m, c, t):
        return m.q_total[c, t] == m.chiller_min[c] * m.on[c, t] + sum(m.q_extra[c, t, s] for s in m.S)

    model.q_total_link = pyo.Constraint(model.C, model.T, rule=q_total_rule)

    def extra_segment_limit_rule(m, c, t, s):
        return m.q_extra[c, t, s] <= m.seg_width[c, s] * m.on[c, t]

    model.extra_segment_limit = pyo.Constraint(model.C, model.T, model.S, rule=extra_segment_limit_rule)

    def max_output_rule(m, c, t):
        return m.q_total[c, t] <= m.chiller_available_max[c, t] * m.on[c, t]

    model.max_output = pyo.Constraint(model.C, model.T, rule=max_output_rule)

    def chiller_power_rule(m, c, t):
        return m.chiller_power[c, t] == m.fixed_power[c] * m.on[c, t] + sum(m.seg_slope[c, s, t] * m.q_extra[c, t, s] for s in m.S)

    model.chiller_power_link = pyo.Constraint(model.C, model.T, rule=chiller_power_rule)

    def startup_rule(m, c, t):
        idx = hours.index(t)
        if idx == 0:
            return m.start[c, t] >= m.on[c, t]
        return m.start[c, t] >= m.on[c, t] - m.on[c, hours[idx - 1]]

    model.startup_logic = pyo.Constraint(model.C, model.T, rule=startup_rule)

    def stop_rule(m, c, t):
        idx = hours.index(t)
        if idx == 0:
            return m.stop[c, t] >= 0.0
        return m.stop[c, t] >= m.on[c, hours[idx - 1]] - m.on[c, t]

    model.shutdown_logic = pyo.Constraint(model.C, model.T, rule=stop_rule)

    model.active_count = pyo.Expression(model.T, rule=lambda m, t: sum(m.on[c, t] for c in m.C))

    model.total_chiller_cooling_link = pyo.Constraint(
        model.T,
        rule=lambda m, t: m.total_cooling_from_chillers[t] == sum(m.q_total[c, t] for c in m.C),
    )

    model.storage_charge_limit = pyo.Constraint(model.T, rule=lambda m, t: m.charge[t] <= m.charge_power_max * m.charge_on[t])
    model.storage_discharge_limit = pyo.Constraint(model.T, rule=lambda m, t: m.discharge[t] <= m.discharge_power_max * m.discharge_on[t])
    model.storage_mode_exclusive = pyo.Constraint(model.T, rule=lambda m, t: m.charge_on[t] + m.discharge_on[t] <= m.storage_enabled)

    def soc_rule(m, t):
        idx = hours.index(t)
        if idx == 0:
            return m.soc[t] == m.initial_soc + m.charge_eff * m.charge[t] - m.discharge[t] / m.discharge_eff
        prev_t = hours[idx - 1]
        return m.soc[t] == m.soc[prev_t] + m.charge_eff * m.charge[t] - m.discharge[t] / m.discharge_eff

    model.storage_state = pyo.Constraint(model.T, rule=soc_rule)
    model.storage_capacity_limit = pyo.Constraint(model.T, rule=lambda m, t: m.soc[t] <= m.storage_capacity)
    model.storage_cyclic = pyo.Constraint(rule=lambda m: m.soc[hours[-1]] == m.initial_soc)

    model.total_supply_link = pyo.Constraint(
        model.T,
        rule=lambda m, t: m.total_supply[t] == m.total_cooling_from_chillers[t] + m.discharge[t] - m.charge[t],
    )

    model.load_rho_limit = pyo.Constraint(model.L, model.T, rule=lambda m, l, t: m.load_rho[l, t] >= m.load_dev_component[l, t] - m.load_eta[t])
    model.robust_demand_balance = pyo.Constraint(
        model.T,
        rule=lambda m, t: m.total_supply[t] + m.unserved[t] >= m.nominal_load[t] + m.load_gamma * m.load_eta[t] + sum(m.load_rho[l, t] for l in m.L),
    )

    def flow_chw_rule(m, t):
        if options.pump_tower_enabled:
            return m.flow_chw[t] >= m.chwp_load_coeff * (m.total_cooling_from_chillers[t] / m.total_installed_cooling_kw) + m.chwp_active_coeff * (m.active_count[t] / len(chiller_names))
        return m.flow_chw[t] == 0.0

    def flow_cw_rule(m, t):
        if options.pump_tower_enabled:
            return m.flow_cw[t] >= m.cwp_load_coeff * (m.total_cooling_from_chillers[t] / m.total_installed_cooling_kw)
        return m.flow_cw[t] == 0.0

    def tower_level_rule(m, t):
        if options.pump_tower_enabled:
            effective_wetbulb = scenario.wetbulb_nominal_c[t] + (scenario.wetbulb_deviation_c[t] if options.robust_wetbulb else 0.0)
            wetbulb_term = max(0.0, effective_wetbulb - aux.tower_reference_wetbulb_c) / 10.0
            return m.tower_level[t] >= m.tower_load_coeff * (m.total_cooling_from_chillers[t] / m.total_installed_cooling_kw) + m.tower_wb_coeff * wetbulb_term
        return m.tower_level[t] == 0.0

    model.flow_chw_link = pyo.Constraint(model.T, rule=flow_chw_rule)
    model.flow_cw_link = pyo.Constraint(model.T, rule=flow_cw_rule)
    model.tower_level_link = pyo.Constraint(model.T, rule=tower_level_rule)

    model.chwp_power_link = pyo.Constraint(model.T, rule=lambda m, t: m.chwp_power[t] == m.chwp_design * m.flow_chw[t])
    model.cwp_power_link = pyo.Constraint(model.T, rule=lambda m, t: m.cwp_power[t] == m.cwp_design * m.flow_cw[t])
    model.tower_power_link = pyo.Constraint(model.T, rule=lambda m, t: m.tower_power[t] == m.tower_design * m.tower_level[t])

    model.grid_power_balance = pyo.Constraint(
        model.T,
        rule=lambda m, t: m.grid_power[t] >= sum(m.chiller_power[c, t] for c in m.C) + m.chwp_power[t] + m.cwp_power[t] + m.tower_power[t],
    )
    model.price_psi_limit = pyo.Constraint(model.T, rule=lambda m, t: m.price_psi[t] >= m.tariff_dev[t] * m.grid_power[t] - m.price_theta)

    energy_cost = sum(model.tariff[t] * model.grid_power[t] for t in model.T)
    startup_cost = sum(model.startup_cost[c] * model.start[c, t] for c in model.C for t in model.T)
    storage_cost = model.storage_cost * sum(model.charge[t] + model.discharge[t] for t in model.T)
    unmet_penalty = case.unmet_cooling_penalty_per_kwh * sum(model.unserved[t] for t in model.T)
    robust_price_cost = model.price_gamma * model.price_theta + sum(model.price_psi[t] for t in model.T)

    model.energy_cost_expr = pyo.Expression(expr=energy_cost)
    model.startup_cost_expr = pyo.Expression(expr=startup_cost)
    model.storage_cost_expr = pyo.Expression(expr=storage_cost)
    model.unmet_penalty_expr = pyo.Expression(expr=unmet_penalty)
    model.robust_price_cost_expr = pyo.Expression(expr=robust_price_cost if options.robust_price else 0.0)
    model.total_cost = pyo.Objective(
        expr=model.energy_cost_expr + model.startup_cost_expr + model.storage_cost_expr + model.unmet_penalty_expr + model.robust_price_cost_expr,
        sense=pyo.minimize,
    )
    return model
