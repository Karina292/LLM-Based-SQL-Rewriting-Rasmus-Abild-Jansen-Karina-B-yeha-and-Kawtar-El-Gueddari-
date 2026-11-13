"""
LLM SQL Rewriting Analysis
Generates figures and summary tables for the paper.
Author: Karina B'yeha
"""

from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Directories

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
FIGURES_DIR = BASE_DIR / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

INPUT_CSV = RESULTS_DIR / "measurements.csv"

# IEEE/ACM 2-column typography
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10,
    "axes.labelsize": 10,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "legend.title_fontsize": 9,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

MODEL_DISPLAY_NAMES = {
    "qwen2.5-coder:7b-instruct-q4_k_m": "Qwen 2.5-Coder 7B",
    "qwen2.5-coder": "Qwen 2.5-Coder 7B",
    "llama3.1:8b-instruct-q4_k_m": "Llama 3.1 8B",
    "llama3.1": "Llama 3.1 8B",
}

FORM_DISPLAY_NAMES = {
    "join": "Explicit JOIN",
    "cte": "Modular CTE",
    "nested": "Nested Subqueries"
}

PALETTE = {
    "Qwen 2.5-Coder 7B": "#2b5c8f",
    "Llama 3.1 8B": "#d95f02",
}

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize model, form, and query identifiers."""
    df = df.copy()
    if "form" in df.columns:
        df["form"] = df["form"].astype(str).str.strip().str.lower().map(lambda x: FORM_DISPLAY_NAMES.get(x, x.upper()))
    if "model" in df.columns:
        df["model"] = df["model"].astype(str).str.strip().str.lower().map(lambda x: MODEL_DISPLAY_NAMES.get(x, x))
    if "query_id" in df.columns:
        df["query_id"] = df["query_id"].astype(str).str.strip().str.lower()
        df["q_num"] = df["query_id"].str.extract(r'(\d+)').astype(float)
        df["query_label"] = df["query_id"].str.upper()
    return df

def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Compute aggregate correctness and speedup metrics."""
    rows = []
    for (model, form), group in df.groupby(["model", "form"]):
        total = len(group)
        correct_group = group[group["correct"] == True]
        n_correct = len(correct_group)
        pct = (n_correct / total) * 100.0 if total > 0 else 0.0
        if n_correct > 0:
            mean_sp = correct_group["speedup"].mean()
            std_sp = correct_group["speedup"].std()
            med_sp = correct_group["speedup"].median()
            plan_pct = (correct_group["plan_changed"].sum() / n_correct) * 100.0
        else:
            mean_sp, std_sp, med_sp, plan_pct = np.nan, np.nan, np.nan, np.nan
        rows.append({
            "model": model, "form": form, "total": total, "n_correct": n_correct,
            "correctness_rate": pct, "mean_speedup": mean_sp, "std_speedup": std_sp,
            "median_speedup": med_sp, "plan_change_rate": plan_pct
        })
    return pd.DataFrame(rows)

def plot_correctness(df: pd.DataFrame, output_dir: Path):
    """Figure: Correctness by form and model."""
    fig, ax = plt.subplots(figsize=(4.8, 3.2), dpi=300)
    agg = df.groupby(["form", "model"])["correct"].mean().reset_index()
    agg["correct_pct"] = agg["correct"] * 100
    order_forms = [f for f in ["Explicit JOIN", "Modular CTE", "Nested Subqueries"] if f in agg["form"].values]
    barplot = sns.barplot(
        data=agg,
        x="form",
        y="correct_pct",
        hue="model",
        order=order_forms,
        palette=PALETTE,
        ax=ax,
        edgecolor="black",
        linewidth=0.8,
        alpha=0.9
    )
    for p in barplot.patches:
        height = p.get_height()
        if not np.isnan(height) and height > 0:
            ax.annotate(
                f"{height:.1f}%",
                (p.get_x() + p.get_width() / 2.0, height + 1.8),
                ha="center", va="bottom", fontsize=8, fontweight="bold", color="#222222"
            )
    ax.set_ylabel("Semantic Correctness (%)", fontweight="bold")
    ax.set_xlabel("Input Structural Syntax", fontweight="bold")
    ax.set_ylim(0, 85)
    ax.set_title("Rewrite Correctness by Structural Form", pad=8)
    ax.legend(title="LLM Evaluated", frameon=True, loc="upper right")
    sns.despine(top=True, right=True)
    plt.tight_layout()
    pdf_path = output_dir / "correctness_by_form_model.pdf"
    plt.savefig(pdf_path)
    plt.close()
    print(f"[FIGURE] Saved: {pdf_path}")

def plot_speedup_distribution(df: pd.DataFrame, output_dir: Path, target_db: str = "tpch_sf01_anon"):
    """Figure: Speedup distribution boxplot for valid rewrites."""
    # Filter by target database
    if "db" in df.columns:
        df_filtered = df[df["db"] == target_db]
    elif "benchmark" in df.columns:
        df_filtered = df[df["benchmark"] == target_db]
    else:
        df_filtered = df
    valid_df = df_filtered[df_filtered["correct"] == True].copy()
    if valid_df.empty:
        print("[WARNING] No valid rewrites found for speedup distribution.")
        return
    fig, ax = plt.subplots(figsize=(5.2, 3.4), dpi=300)
    order_forms = [f for f in ["Explicit JOIN", "Modular CTE", "Nested Subqueries"] if f in valid_df["form"].values]
    sns.boxplot(
        data=valid_df,
        x="form",
        y="speedup",
        hue="model",
        order=order_forms,
        palette=PALETTE,
        ax=ax,
        showmeans=True,
        meanprops={"marker": "^", "markerfacecolor": "white", "markeredgecolor": "black", "markersize": 6},
        flierprops={"marker": "o", "markersize": 3, "alpha": 0.4}
    )
    ax.axhline(1.0, color="#d90429", linestyle="--", linewidth=1.2, label="Parity Baseline (1.0×)")
    ax.set_ylabel(r"Speedup Ratio ($T_{\mathrm{base}} \,/\, T_{\mathrm{rewrite}}$)", fontweight="bold")
    ax.set_xlabel("Input Structural Syntax", fontweight="bold")
    ax.set_title("Execution Speedup Distribution on Valid Rewrites", pad=8)
    # Focus axis around typical speedup ratios
    ax.set_ylim(0.4, 2.6)
    ax.legend(title="LLM Evaluated", frameon=True, loc="upper right")
    sns.despine(top=True, right=True)
    plt.tight_layout()
    pdf_path = output_dir / "speedup_distribution.pdf"
    plt.savefig(pdf_path)
    plt.close()
    print(f"[FIGURE] Saved: {pdf_path}")

def plot_correctness_by_query(df: pd.DataFrame, output_dir: Path):
    """Figure: Correctness across 15 queries (compact 1-column layout)."""
    agg = df.groupby(["query_label", "q_num", "form"])["correct"].mean().reset_index()
    agg["correct_pct"] = agg["correct"] * 100
    agg = agg.sort_values(by=["q_num", "form"])
    query_order = sorted(agg["query_label"].unique(), key=lambda x: int(x.replace("Q", "")))

    # Exact 1-column dimensions (3.4 inches width)
    fig, ax = plt.subplots(figsize=(3.4, 2.6), dpi=300)

    form_palette = {
        "Explicit JOIN": "#2b5c8f",
        "Modular CTE": "#41b6c4",
        "Nested Subqueries": "#d95f02"
    }

    sns.barplot(
        data=agg,
        x="query_label",
        y="correct_pct",
        hue="form",
        order=query_order,
        palette=form_palette,
        ax=ax,
        edgecolor="black",
        linewidth=0.5,
        errorbar=None
    )

    ax.set_xlabel("TPC-H Query", fontweight="bold", fontsize=8)
    ax.set_ylabel("Correctness (%)", fontweight="bold", fontsize=8)
    ax.set_ylim(0, 105)
    ax.tick_params(axis='x', rotation=45, labelsize=7)
    ax.tick_params(axis='y', labelsize=7)
    ax.legend(title=None, frameon=True, fontsize=6.5, loc="upper right", ncol=1)

    sns.despine(top=True, right=True)
    plt.tight_layout()

    pdf_path = output_dir / "correctness_by_query.pdf"
    plt.savefig(pdf_path)
    plt.close()
    print(f"[FIGURE] Saved compact 1-column figure: {pdf_path}")

def export_latex_table(summary_df: pd.DataFrame, output_dir: Path):
    """Export summary results table to LaTeX format."""
    table_path = output_dir / "summary_table.tex"
    with open(table_path, "w", encoding="utf-8") as f:
        f.write("% Auto-generated by analysis.py - INF2204\n")
        f.write("\\begin{table*}[t]\n\\centering\n\\small\n")
        f.write("\\begin{tabular}{llcccccc}\n\\toprule\n")
        f.write("\\textbf{Model} & \\textbf{Form} & \\textbf{Total} & \\textbf{$n_{\\text{correct}}$} & \\textbf{Correctness (\\%)} & \\textbf{Mean Speedup} & \\textbf{Median} & \\textbf{Plan Changed (\\%)} \\\\\n\\midrule\n")
        for _, r in summary_df.iterrows():
            m_str = f"{r['mean_speedup']:.2f} $\\pm$ {r['std_speedup']:.2f}" if pd.notnull(r['mean_speedup']) else "NA"
            med_str = f"{r['median_speedup']:.2f}" if pd.notnull(r['median_speedup']) else "NA"
            pl_str = f"{r['plan_change_rate']:.1f}\\%" if pd.notnull(r['plan_change_rate']) else "NA"
            f.write(f"{r['model']} & {r['form']} & {r['total']} & {r['n_correct']} & {r['correctness_rate']:.1f}\\% & {m_str} & {med_str} & {pl_str} \\\\\n")
        f.write("\\bottomrule\n\\end{tabular}\n")
        f.write("\\caption{Summary of experimental results across structural query forms and LLMs ($N=5$ per combination). Combinations with zero valid rewrites are designated as NA.}\n")
        f.write("\\label{tab:summary}\n\\end{table*}\n")
    print(f"[LATEX] Saved: {table_path}")

def main():
    if not INPUT_CSV.exists() or INPUT_CSV.stat().st_size == 0:
        raise FileNotFoundError(f"Missing measurements file: {INPUT_CSV}")
    raw_df = pd.read_csv(INPUT_CSV)
    df = clean_dataframe(raw_df)
    # Filter for primary benchmark (SF 0.1 without secondary indexes)
    db_col = "db" if "db" in df.columns else ("benchmark" if "benchmark" in df.columns else None)
    if db_col and "tpch_sf01_anon" in df[db_col].values:
        main_df = df[df[db_col] == "tpch_sf01_anon"].copy()
    else:
        main_df = df.copy()
    summary_df = compute_metrics(main_df)
    # Generate paper figures and tables
    plot_correctness(main_df, FIGURES_DIR)
    plot_speedup_distribution(df, FIGURES_DIR, target_db="tpch_sf01_anon")
    plot_correctness_by_query(main_df, FIGURES_DIR)
    export_latex_table(summary_df, FIGURES_DIR)
    print("\n[SUCCESS] All paper figures and tables generated successfully.")

if __name__ == "__main__":
    main()