# PAPER PLAN

## Title

Robust day-ahead scheduling of a heterogeneous multi-chiller plant with thermal storage using a reproducible Pyomo-MILP framework

## Core Problem

How can a multi-chiller plant be scheduled day-ahead under load and tariff uncertainty while preserving cooling adequacy and maintaining a tractable, reproducible optimization workflow?

## Core Claims

1. A compact full-plant Pyomo MILP can represent chillers, storage, pumps, and cooling-tower auxiliaries in a unified scheduling framework.
2. Budgeted robust optimization materially improves out-of-sample cooling adequacy relative to deterministic MILP scheduling.
3. Storage reduces the nominal cost premium of robust scheduling.
4. Equipment heterogeneity and auxiliary loads materially affect conclusions and should not be abstracted away.

## Evidence Map

- Claim 1: formulation in `sections/3_method.tex`
- Claim 2: benchmark table and cost-robustness tradeoff figure
- Claim 3: comparison between `robust_no_storage` and `robust_with_storage`
- Claim 4: identical-chiller and no-pump-tower ablations

## Figures

1. Dispatch comparison
2. Cost-robustness tradeoff
3. Grid power and storage state comparison
4. Cost breakdown
5. Load-gamma sensitivity
6. Storage-capacity sensitivity

## Target Narrative

This is a methodology and benchmark paper for journal submission, not a plant-specific field validation paper and not a real-time MPC paper.
