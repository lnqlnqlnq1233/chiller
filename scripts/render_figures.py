from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model_tsep.visualization import render_ablation_gallery, render_benchmark_gallery


if __name__ == "__main__":
    render_benchmark_gallery()
    render_ablation_gallery()
    print(f"Figure gallery rendered under {Path('outputs').resolve()}")
