# Robust Pyomo-MILP Multi-Chiller Plant

This workspace implements a research scaffold for a day-ahead robust MILP of a
heterogeneous multi-chiller plant with:

- 3 large chillers and 1 small chiller
- chilled-water storage
- chilled-water pumps
- condenser-water pumps
- cooling tower operating levels
- budgeted robust optimization for cooling-load and tariff uncertainty

The code is organized to support three workflows:

1. Generate a semi-synthetic benchmark plant case
2. Solve deterministic and robust Pyomo MILP scheduling problems
3. Compare against a rule-based baseline and export paper-ready plots/tables

## Quick Start

Run the benchmark comparison:

```powershell
python scripts/run_benchmark.py
```

Run ablations:

```powershell
python scripts/run_ablations.py
```

Outputs are written under `outputs/`.

## Project Layout

- `model_tsep/`
  Core package with case generation, MILP model, solver wrappers, reporting,
  and experiment runners.
- `scripts/`
  Entry points for benchmark and ablation experiments.
- `docs/`
  Research-facing notes for literature positioning and paper structure.

## Main Interfaces

- `CaseConfig`
  Semi-synthetic plant definition, equipment parameters, performance segments,
  tariff, weather, and load decomposition.
- `ScenarioSet`
  Nominal inputs, uncertainty bounds, and Bertsimas-Sim budgets.
- `ResultBundle`
  Objective breakdown, time-series dispatch, KPIs, and solver status.
