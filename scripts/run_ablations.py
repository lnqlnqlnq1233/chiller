from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model_tsep.experiments import run_ablations


if __name__ == "__main__":
    results = run_ablations()
    print(f"Ablations completed. Results written to {Path('outputs/ablations').resolve()}")
    for bundle in results:
        print(f"{bundle.method}: total_cost={bundle.kpis['total_cost']:.2f}, avg_cop={bundle.kpis['avg_cop']:.3f}")
