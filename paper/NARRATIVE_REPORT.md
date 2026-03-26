# NARRATIVE REPORT

The project develops a robust day-ahead scheduling framework for a heterogeneous multi-chiller plant with thermal storage. The implementation is centered on Pyomo and mixed-integer linear programming so that the method remains transparent, reproducible, and easy to extend.

The benchmark plant contains three large chillers, one small chiller, chilled-water storage, chilled-water pumps, condenser-water pumps, and cooling-tower auxiliaries. A 24-hour semi-synthetic cooling-load profile and time-of-use tariff profile are used to evaluate four methods: a rule-based baseline, a deterministic MILP without storage, a robust MILP without storage, and a robust MILP with storage.

The benchmark results show the expected nominal-versus-robustness tradeoff. The deterministic MILP achieves the lowest nominal total cost at 5706.4 but exhibits an out-of-sample mean shortage of 737.4 kWh. The robust no-storage model increases total cost to 6128.2 while reducing out-of-sample mean shortage to 69.5 kWh. Adding storage lowers the robust total cost to 6002.1 without worsening the shortage metric. The rule-based baseline is dominated on both cost and efficiency.

Ablation studies further support the paper's thesis. Increasing the load uncertainty budget from 0.0 to 2.2 monotonically decreases out-of-sample shortage from 737.4 kWh to 2.8 kWh while increasing total cost from 5584.7 to 6092.8. Enlarging storage capacity from 450 kWh to 1400 kWh lowers total cost from 6062.0 to 5955.2. Assuming identical chillers worsens average COP and increases cost, while removing pump and tower loads produces unrealistically optimistic results.

The paper should therefore argue for robust full-plant scheduling as a practical middle ground between rule-based operation and infrastructure-heavy predictive control pipelines. Its contribution is a transparent scheduling formulation and experiment pipeline rather than a claim of universal optimal control.
