import unittest

from model_tsep.baseline import run_rule_based_baseline
from model_tsep.model_builder import ModelOptions
from model_tsep.solver import solve_case
from model_tsep.synthetic_case import create_benchmark_case


class SmokeTest(unittest.TestCase):
    def test_rule_based_runs(self) -> None:
        case = create_benchmark_case()
        result = run_rule_based_baseline(case)
        self.assertEqual(len(result.dispatch), 24)
        self.assertGreater(result.kpis["total_cost"], 0.0)

    def test_deterministic_milp_runs(self) -> None:
        case = create_benchmark_case()
        result = solve_case(
            case,
            method="deterministic_smoke",
            options=ModelOptions(robust_load=False, robust_price=False, storage_enabled=True, pump_tower_enabled=True),
        )
        self.assertEqual(len(result.dispatch), 24)
        self.assertLessEqual(result.kpis["total_unserved_kwh"], 1e-6)

    def test_full_robust_milp_runs(self) -> None:
        case = create_benchmark_case()
        result = solve_case(
            case,
            method="robust_full_smoke",
            options=ModelOptions(
                robust_load=True,
                robust_price=True,
                robust_wetbulb=True,
                storage_enabled=True,
                pump_tower_enabled=True,
            ),
        )
        self.assertEqual(len(result.dispatch), 24)
        self.assertGreater(result.kpis["total_cost"], 0.0)


if __name__ == "__main__":
    unittest.main()
