from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _load_dispatch_map(folder: Path, methods: list[str]) -> dict[str, pd.DataFrame]:
    return {method: pd.read_csv(folder / f"{method}_dispatch.csv") for method in methods}


def _cooling_columns(dispatch: pd.DataFrame) -> list[str]:
    return [col for col in dispatch.columns if col.endswith("_cooling_kw") and not col.startswith("chiller_")]


def render_benchmark_gallery(output_dir: str | Path = "outputs/benchmark") -> None:
    folder = Path(output_dir)
    summary = pd.read_csv(folder / "benchmark_summary.csv")
    methods = summary["method"].tolist()
    dispatch_map = _load_dispatch_map(folder, methods)

    fig, ax = plt.subplots(figsize=(10, 5))
    components = ["energy_cost", "startup_cost", "storage_cost", "robust_price_cost", "unmet_penalty"]
    bottom = np.zeros(len(methods))
    for component in components:
        values = []
        for method in methods:
            breakdown = pd.read_csv(folder / f"{method}_objective_breakdown.csv", index_col=0)
            values.append(float(breakdown.loc[component, "value"]) if component in breakdown.index else 0.0)
        ax.bar(methods, values, bottom=bottom, label=component)
        bottom += np.array(values)
    ax.set_ylabel("Cost")
    ax.set_title("Benchmark Cost Breakdown")
    ax.legend()
    plt.xticks(rotation=15)
    fig.tight_layout()
    fig.savefig(folder / "benchmark_cost_breakdown.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(summary["total_cost"], summary["oos_mean_shortage_kwh"], s=110)
    for _, row in summary.iterrows():
        ax.annotate(row["method"], (row["total_cost"], row["oos_mean_shortage_kwh"]), xytext=(6, 4), textcoords="offset points")
    ax.set_xlabel("Total cost")
    ax.set_ylabel("Out-of-sample mean shortage (kWh)")
    ax.set_title("Cost-Robustness Tradeoff")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(folder / "benchmark_cost_robustness_tradeoff.png", dpi=180)
    plt.close(fig)

    n_methods = len(methods)
    ncols = 2
    nrows = int(np.ceil(n_methods / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 4.2 * nrows), sharex=True, sharey=True)
    axes = np.atleast_1d(axes).flatten()
    for ax, method in zip(axes, methods):
        dispatch = dispatch_map[method]
        hours = dispatch["hour"].to_numpy()
        cooling_cols = _cooling_columns(dispatch)
        stacks = [dispatch[col].to_numpy() for col in cooling_cols]
        labels = [col.replace("_cooling_kw", "") for col in cooling_cols]
        if stacks:
            ax.stackplot(hours, *stacks, labels=labels, alpha=0.8)
        ax.plot(hours, dispatch["load_kw"], color="black", linewidth=2.0, label="Load")
        ax.plot(hours, dispatch["discharge_kw"], color="tab:cyan", linestyle="--", linewidth=1.4, label="Storage discharge")
        ax.plot(hours, -dispatch["charge_kw"], color="tab:purple", linestyle=":", linewidth=1.4, label="Storage charge")
        ax.set_title(method)
        ax.set_xlabel("Hour")
        ax.set_ylabel("Cooling (kW)")
        ax.grid(alpha=0.2)
    for ax in axes[len(methods):]:
        ax.axis("off")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4)
    fig.suptitle("Dispatch Comparison Across Methods", y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(folder / "benchmark_dispatch_comparison.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 4.2 * nrows), sharex=True)
    axes = np.atleast_1d(axes).flatten()
    for ax, method in zip(axes, methods):
        dispatch = dispatch_map[method]
        hours = dispatch["hour"].to_numpy()
        ax.plot(hours, dispatch["grid_power_kw"], color="tab:red", label="Grid power")
        ax2 = ax.twinx()
        ax2.plot(hours, dispatch["soc_kwh"], color="tab:blue", label="SOC")
        ax.set_title(method)
        ax.set_xlabel("Hour")
        ax.set_ylabel("Power (kW)", color="tab:red")
        ax2.set_ylabel("SOC (kWh)", color="tab:blue")
        ax.grid(alpha=0.2)
    for ax in axes[len(methods):]:
        ax.axis("off")
    fig.suptitle("Grid Power and Storage State Comparison", y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(folder / "benchmark_grid_soc_comparison.png", dpi=180)
    plt.close(fig)

    metrics = ["total_cost", "peak_grid_power_kw", "avg_cop", "oos_mean_shortage_kwh"]
    heat = summary[metrics].copy()
    heat["avg_cop"] = heat["avg_cop"].max() - heat["avg_cop"]
    heat_norm = (heat - heat.min()) / (heat.max() - heat.min() + 1e-9)
    fig, ax = plt.subplots(figsize=(8, 4))
    im = ax.imshow(heat_norm.to_numpy(), cmap="YlOrRd", aspect="auto")
    ax.set_xticks(range(len(metrics)))
    ax.set_xticklabels(metrics, rotation=20)
    ax.set_yticks(range(len(methods)))
    ax.set_yticklabels(methods)
    ax.set_title("Normalized Benchmark Risk/Cost Heatmap")
    fig.colorbar(im, ax=ax, shrink=0.9)
    fig.tight_layout()
    fig.savefig(folder / "benchmark_kpi_heatmap.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(len(methods), 1, figsize=(12, 7), sharex=True)
    if len(methods) == 1:
        axes = [axes]
    for ax, method in zip(axes, methods):
        dispatch = dispatch_map[method]
        on_cols = [col for col in dispatch.columns if col.endswith("_on")]
        if on_cols:
            matrix = dispatch[on_cols].to_numpy().T
            im = ax.imshow(matrix, cmap="Greens", aspect="auto", vmin=0, vmax=1)
            ax.set_yticks(range(len(on_cols)))
            ax.set_yticklabels([col.replace("_on", "") for col in on_cols])
        ax.set_title(method)
        ax.set_ylabel("Chiller")
    axes[-1].set_xlabel("Hour")
    fig.suptitle("Chiller Commitment Heatmap", y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(folder / "benchmark_commitment_heatmap.png", dpi=180)
    plt.close(fig)


def render_ablation_gallery(output_dir: str | Path = "outputs/ablations") -> None:
    folder = Path(output_dir)
    summary = pd.read_csv(folder / "ablation_summary.csv")

    gamma_df = summary[summary["method"].str.startswith("load_gamma")].sort_values("ablation_gamma")
    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.plot(gamma_df["ablation_gamma"], gamma_df["total_cost"], marker="o", color="tab:red", label="Total cost")
    ax1.set_xlabel("Load uncertainty budget gamma")
    ax1.set_ylabel("Total cost", color="tab:red")
    ax2 = ax1.twinx()
    ax2.plot(gamma_df["ablation_gamma"], gamma_df["oos_mean_shortage_kwh"], marker="s", color="tab:blue", label="OOS shortage")
    ax2.set_ylabel("Out-of-sample mean shortage (kWh)", color="tab:blue")
    ax1.set_title("Robustness Budget Sensitivity")
    ax1.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(folder / "ablation_load_gamma_sensitivity.png", dpi=180)
    plt.close(fig)

    storage_df = summary.dropna(subset=["storage_capacity_kwh"]).sort_values("storage_capacity_kwh")
    if not storage_df.empty:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(storage_df["storage_capacity_kwh"], storage_df["total_cost"], marker="o", label="Total cost")
        ax.plot(storage_df["storage_capacity_kwh"], storage_df["peak_grid_power_kw"], marker="s", label="Peak grid power")
        ax.set_xlabel("Storage capacity (kWh)")
        ax.set_title("Storage Capacity Sensitivity")
        ax.legend()
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(folder / "ablation_storage_sensitivity.png", dpi=180)
        plt.close(fig)

    compare_cols = ["identical_chillers", "no_pump_tower"]
    compare_methods = [method for method in compare_cols if (summary["method"] == method).any()]
    if compare_methods:
        compare_df = summary[summary["method"].isin(compare_methods)].copy()
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
        axes[0].bar(compare_df["method"], compare_df["total_cost"], color=["tab:orange", "tab:green"])
        axes[0].set_title("Architecture Ablation: Total Cost")
        axes[0].tick_params(axis="x", rotation=15)
        axes[1].bar(compare_df["method"], compare_df["avg_cop"], color=["tab:orange", "tab:green"])
        axes[1].set_title("Architecture Ablation: Average COP")
        axes[1].tick_params(axis="x", rotation=15)
        fig.tight_layout()
        fig.savefig(folder / "ablation_architecture_comparison.png", dpi=180)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(summary["total_cost"], summary["oos_mean_shortage_kwh"], s=100, c=summary["avg_cop"], cmap="viridis")
    for _, row in summary.iterrows():
        ax.annotate(row["method"], (row["total_cost"], row["oos_mean_shortage_kwh"]), xytext=(5, 4), textcoords="offset points", fontsize=8)
    ax.set_xlabel("Total cost")
    ax.set_ylabel("Out-of-sample mean shortage (kWh)")
    ax.set_title("Ablation Frontier")
    fig.colorbar(ax.collections[0], ax=ax, label="Average COP")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(folder / "ablation_frontier.png", dpi=180)
    plt.close(fig)
