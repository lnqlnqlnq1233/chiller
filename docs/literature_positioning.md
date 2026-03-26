# Literature Positioning

This project is positioned at the intersection of full-plant scheduling,
cooling-system control, and robust optimization.

## Five Related-Work Clusters

| Cluster | Representative references | Takeaway | Gap left for this project |
|---|---|---|---|
| Chiller plant global optimization and sequencing | Niu et al. 2023; Bai et al. 2024 | Strong on setpoint and sequencing optimization with calibrated simulation | Less emphasis on open, reproducible Pyomo MILP with explicit startup, storage, and uncertainty |
| Modelica-based digital twin / calibration | Fu et al. 2019 | Strong model fidelity and root-cause analysis | Control and optimization layers are often external, simulation-heavy, and harder to reproduce |
| MPC for chillers and data-center cooling | Zhu et al. 2023; Zhao et al. 2024 | Strong dynamic control and energy savings in case studies | Often uses MPC/PSO/LSTM stacks rather than a compact scheduling MILP |
| Storage-coupled chiller scheduling | Zhu et al. 2023 | Shows storage can materially improve energy cost and PUE | Commonly tied to one control architecture or one facility context |
| Robust/stochastic chiller optimization | Sadat-Mohammadi et al. 2020; Saeedi et al. 2019 | Recognizes uncertainty in load and prices | Usually narrower system boundaries or different plant assumptions |

## Intended Contribution

The contribution claim for this codebase and the related paper should be:

> A reproducible Pyomo-based robust MILP framework for day-ahead scheduling of
> a heterogeneous multi-chiller plant with storage and auxiliary equipment under
> cooling-load and tariff uncertainty.

The claim should not be framed as a universal HVAC controller. The strength is
the combination of:

- explicit equipment-level mixed-integer scheduling
- system boundary beyond chillers alone
- budgeted robust optimization that stays MILP-solvable
- reproducible experiment pipeline for semi-synthetic benchmark studies
