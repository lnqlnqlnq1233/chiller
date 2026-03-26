from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .schemas import ResultBundle


def export_result_bundle(bundle: ResultBundle, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle.dispatch.to_csv(output_dir / f"{bundle.method}_dispatch.csv", index=False)
    pd.Series(bundle.objective_breakdown, name="value").to_csv(output_dir / f"{bundle.method}_objective_breakdown.csv")
    pd.Series(bundle.kpis, name="value").to_csv(output_dir / f"{bundle.method}_kpis.csv")

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(bundle.dispatch["hour"], bundle.dispatch["load_kw"], label="Load")
    ax.plot(bundle.dispatch["hour"], bundle.dispatch["cooling_supply_kw"], label="Supply")
    ax.plot(bundle.dispatch["hour"], bundle.dispatch["unserved_kw"], label="Unserved")
    ax.set_xlabel("Hour")
    ax.set_ylabel("Cooling (kW)")
    ax.set_title(f"{bundle.method}: Cooling Balance")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / f"{bundle.method}_cooling_balance.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(bundle.dispatch["hour"], bundle.dispatch["soc_kwh"], label="Storage SOC")
    ax.bar(bundle.dispatch["hour"], bundle.dispatch["charge_kw"], alpha=0.35, label="Charge")
    ax.bar(bundle.dispatch["hour"], bundle.dispatch["discharge_kw"], alpha=0.35, label="Discharge")
    ax.set_xlabel("Hour")
    ax.set_ylabel("kWh / kW")
    ax.set_title(f"{bundle.method}: Storage Trajectory")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / f"{bundle.method}_storage.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(bundle.dispatch["hour"], bundle.dispatch["grid_power_kw"], label="Grid power")
    ax.plot(bundle.dispatch["hour"], bundle.dispatch["tariff"], label="Tariff")
    ax.set_xlabel("Hour")
    ax.set_title(f"{bundle.method}: Power and Tariff")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / f"{bundle.method}_power_tariff.png", dpi=180)
    plt.close(fig)


def export_comparison_table(results: list[ResultBundle], output_path: Path) -> pd.DataFrame:
    rows = []
    for bundle in results:
        row = {"method": bundle.method}
        row.update(bundle.kpis)
        rows.append(row)
    table = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output_path, index=False)
    return table
