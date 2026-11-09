"""
INF2204 - Assignment 3 / Research Project
Author: Karina (Analysis & Writing Lead)

This script processes 'baselines.csv' and 'measurements.csv',
computes statistical metrics, and generates clean, publication-ready
figures with readable labels and LaTeX tables for the final paper.
"""

from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import os

# ============================================================
# CONFIGURATION & DIRECTORIES
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
FIGURES_DIR = BASE_DIR / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

INPUT_CSV = RESULTS_DIR / "measurements.csv"
BASELINES_CSV = RESULTS_DIR / "baselines.csv"

# Professional typography & style for IEEE/ACM 2-column papers
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams.update({
    "font.family": "serif",  # Stile tipografico classico per paper
    "font.size": 10,
    "axes.labelsize": 10,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "legend.title_fontsize": 9,
    "figure.titlesize": 12,
    "pdf.fonttype": 42,  # TrueType incorporato nel PDF (richiesto da ACM/IEEE)
    "ps.fonttype": 42,
})

# Mappe per nomi puliti e leggibili nei grafici
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
    "Qwen 2.5-Coder 7B": "#2b5c8f",  # Blu scuro accademico
    "Llama 3.1 8B": "#d95f02",  # Arancione scuro accademico
}


# ============================================================
# HELPER: CLEAN & NORMALIZE LABELS
# ============================================================

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Pulisce e rinomina colonne e valori per i grafici."""
    df = df.copy()
    if "form" in df.columns:
        df["form_raw"] = df["form"].astype(str).str.strip().str.lower()
        df["form"] = df["form_raw"].map(lambda x: FORM_DISPLAY_NAMES.get(x, x.upper()))

    if "model" in df.columns:
        df["model_raw"] = df["model"].astype(str).str.strip().str.lower()
        df["model"] = df["model_raw"].map(lambda x: MODEL_DISPLAY_NAMES.get(x, x))

    if "query_id" in df.columns:
        df["query_id"] = df["query_id"].astype(str).str.strip().str.lower()
        # Estrae il numero per ordinare Q1, Q2... Q21 in ordine numerico naturale
        df["q_num"] = df["query_id"].str.extract(r'(\d+)').astype(float)
        df["query_label"] = df["query_id"].str.upper()
    return df


# ============================================================
# 1. BASELINE ANALYSIS
# ============================================================

def analyze_baselines(file_path: Path, output_dir: Path):
    if not file_path.exists():
        print(f"[INFO] '{file_path}' not found. Skipping baseline analysis.")
        return

    print("\n" + "=" * 60)
    print("BASELINE RUNTIME ANALYSIS (Original Queries)")
    print("=" * 60)

    df_base = pd.read_csv(file_path)
    if df_base.empty:
        print("[WARNING] baselines.csv is empty!")
        return

    df_base = clean_dataframe(df_base)
    dbs = df_base["db"].unique() if "db" in df_base.columns else ["default"]

    for db_name in dbs:
        sub = df_base[df_base["db"] == db_name] if "db" in df_base.columns else df_base
        pivot = sub.pivot_table(index="query_label", columns="form", values="median_ms").round(2)

        cols = [c for c in ["Explicit JOIN", "Modular CTE", "Nested Subqueries"] if c in pivot.columns]
        pivot = pivot[cols]

        clean_db = str(db_name).replace(".", "_")
        tbl_path = output_dir / f"baseline_{clean_db}.tex"

        with open(tbl_path, "w", encoding="utf-8") as f:
            f.write(f"% Baseline Runtimes for {db_name}\n")
            f.write("\\begin{table}[h]\n\\centering\n\\small\n")
            f.write("\\begin{tabular}{l" + "c" * len(cols) + "}\n\\toprule\n")
            f.write("\\textbf{Query} & " + " & ".join([f"\\textbf{{{c}}}" for c in cols]) + " \\\\\n\\midrule\n")
            for q_id, row in pivot.iterrows():
                vals = [f"{row[c]:.2f}" if pd.notnull(row[c]) else "NA" for c in cols]
                f.write(f"{str(q_id)} & " + " & ".join(vals) + " \\\\\n")
            f.write("\\bottomrule\n\\end{tabular}\n")
            f.write(f"\\caption{{Baseline execution runtimes (median ms) across structural forms on {db_name}.}}\n")
            f.write(f"\\label{{tab:baseline_{clean_db}}}\n\\end{{table}}\n")

        print(f"[LATEX] Saved baseline runtime table for '{db_name}' to: {tbl_path}")


# ============================================================
# 2. METRICS & SPEEDUP CLASSIFICATION
# ============================================================

def compute_metrics(df: pd.DataFrame):
    print("\n" + "=" * 60)
    print("LLM REWRITE ANALYSIS SUMMARY")
    print("=" * 60)

    summary_rows = []
    for (model, form), group in df.groupby(["model", "form"]):
        total = len(group)
        correct_group = group[group["correct"] == True]
        n_correct = len(correct_group)
        pct = (n_correct / total) * 100.0

        if n_correct > 0:
            mean_sp = correct_group["speedup"].mean()
            std_sp = correct_group["speedup"].std()
            med_sp = correct_group["speedup"].median()
            plan_pct = (correct_group["plan_changed"].sum() / n_correct) * 100.0
        else:
            mean_sp, std_sp, med_sp, plan_pct = np.nan, np.nan, np.nan, np.nan

        summary_rows.append({
            "model": model, "form": form, "total": total, "n_correct": n_correct,
            "correctness_rate": pct, "mean_speedup": mean_sp, "std_speedup": std_sp,
            "median_speedup": med_sp, "plan_change_rate": plan_pct
        })

    summary_df = pd.DataFrame(summary_rows)
    print(summary_df.to_string(index=False))
    return summary_df


def classify_speedup(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["speedup_class"] = "not_evaluated"
    valid = (df["correct"].eq(True) & df["speedup"].notna())

    df.loc[valid, "speedup_class"] = "no_significant_speedup"
    faster = valid & (df["speedup"] > 1.05)
    df.loc[faster, "speedup_class"] = "faster"

    probably_noise = (
            valid
            & (df["speedup"] > 1.05)
            & (df["speedup"] <= 1.10)
            & df["plan_changed"].eq(False)
    )
    df.loc[probably_noise, "speedup_class"] = "probably_noise"

    print("\nSPEEDUP CLASSIFICATION")
    print("=" * 60)
    print(df.loc[valid, "speedup_class"].value_counts().to_string())
    return df


# ============================================================
# 3. VISUALIZATION & FIGURE GENERATION
# ============================================================

def plot_correctness(df: pd.DataFrame, output_dir: Path):
    """
    Figure 1: Overall correctness by form & model.
    Aggiunge percentuali sopra le barre ed etichette pulite.
    """
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

    # Scritta con percentuale sopra ogni barra
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

    # Rimuove il bordo superiore e destro per un look pulito
    sns.despine(top=True, right=True)

    plt.tight_layout()
    pdf_path = output_dir / "correctness_by_form_model.pdf"
    plt.savefig(pdf_path)
    plt.savefig(output_dir / "correctness_by_form_model.png")
    plt.close()
    print(f"[FIGURE] Saved clean: {pdf_path}")


def plot_speedup_distribution(df: pd.DataFrame, output_dir: Path):
    """
    Figure 2: Speedup distribution boxplot.
    Etichette LaTeX chiare e asse centrato attorno a 1.0x.
    """
    valid_df = df[df["correct"] == True].copy()
    if valid_df.empty:
        print("[WARNING] No valid rewrites available to plot speedup distribution.")
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

    # Linea rossa a 1.0x (Baseline)
    ax.axhline(1.0, color="#d90429", linestyle="--", linewidth=1.2, label="Parity Baseline (1.0×)")

    ax.set_ylabel(r"Speedup Ratio ($T_{\mathrm{base}} \,/\, T_{\mathrm{rewrite}}$)", fontweight="bold")
    ax.set_xlabel("Input Structural Syntax", fontweight="bold")
    ax.set_title("Execution Speedup Distribution on Valid Rewrites", pad=8)

    # Zoom intelligente se ci sono outlier enormi per non schiacciare le scatole
    q_low = valid_df["speedup"].quantile(0.01)
    q_high = valid_df["speedup"].quantile(0.99)
    ax.set_ylim(max(0.4, q_low - 0.2), min(3.0, q_high + 0.4))

    ax.legend(title="LLM Evaluated", frameon=True, loc="upper right")
    sns.despine(top=True, right=True)

    plt.tight_layout()
    pdf_path = output_dir / "speedup_distribution.pdf"
    plt.savefig(pdf_path)
    plt.savefig(output_dir / "speedup_distribution.png")
    plt.close()
    print(f"[FIGURE] Saved clean: {pdf_path}")


def plot_correctness_by_query(df: pd.DataFrame, output_dir: Path):
    """
    Versione compatta perfetta per singola colonna LaTeX.
    """
    agg = (
        df.groupby(["query_label", "q_num", "form"])["correct"]
        .mean()
        .reset_index()
    )
    agg["correct_pct"] = agg["correct"] * 100
    agg = agg.sort_values(by=["q_num", "form"])
    query_order = sorted(agg["query_label"].unique(), key=lambda x: int(x.replace("Q", "")))

    # Dimensioni ideali per una colonna: circa 3.4 pollici di larghezza
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
    plt.savefig(output_dir / "correctness_by_query.png")
    plt.close()
    print(f"[FIGURE] Saved compact 1-column figure: {pdf_path}")

def export_correctness_by_query(df: pd.DataFrame, output_dir: Path):
    correctness = (
        df.groupby(["query_label", "q_num", "form", "model"], dropna=False)
        .agg(
            total=("correct", "size"),
            n_correct=("correct", "sum"),
            correctness_rate=("correct", "mean")
        )
        .reset_index()
    )
    correctness["correctness_pct"] = correctness["correctness_rate"] * 100
    correctness = correctness.sort_values(by=["q_num", "form"])

    csv_path = output_dir / "correctness_by_query.csv"
    correctness.to_csv(csv_path, index=False)

    pivot = correctness.pivot(
        index="query_label",
        columns=["model", "form"],
        values="correctness_pct"
    ).round(1)

    table_path = output_dir / "correctness_by_query_pivot.csv"
    pivot.to_csv(table_path)
    print(f"[ANALYSIS] Exported: {table_path}")


def export_latex_table(summary_df: pd.DataFrame, output_dir: Path):
    table_path = output_dir / "summary_table.tex"
    with open(table_path, "w", encoding="utf-8") as f:
        f.write("% Auto-generated by analysis.py - INF2204\n")
        f.write("\\begin{table*}[t]\n\\centering\n\\small\n")
        f.write("\\begin{tabular}{llcccccc}\n\\toprule\n")
        f.write(
            "\\textbf{Model} & \\textbf{Form} & \\textbf{Total} & \\textbf{$n_{\\text{correct}}$} & \\textbf{Correctness (\\%)} & \\textbf{Mean Speedup} & \\textbf{Median} & \\textbf{Plan Changed (\\%)} \\\\\n\\midrule\n")
        for _, r in summary_df.iterrows():
            m_str = f"{r['mean_speedup']:.2f} $\\pm$ {r['std_speedup']:.2f}" if pd.notnull(r['mean_speedup']) else "NA"
            med_str = f"{r['median_speedup']:.2f}" if pd.notnull(r['median_speedup']) else "NA"
            pl_str = f"{r['plan_change_rate']:.1f}\\%" if pd.notnull(r['plan_change_rate']) else "NA"
            f.write(
                f"{r['model']} & {r['form']} & {r['total']} & {r['n_correct']} & {r['correctness_rate']:.1f}\\% & {m_str} & {med_str} & {pl_str} \\\\\n")
        f.write("\\bottomrule\n\\end{tabular}\n")
        f.write(
            "\\caption{Summary of experimental results across structural query forms and LLMs ($N=5$ per combination). Combinations with zero valid rewrites are designated as NA (C15).}\n")
        f.write("\\label{tab:summary}\n\\end{table*}\n")
    print(f"[LATEX] Saved summary table to: {table_path}")


# ============================================================
# MAIN ENTRYPOINT
# ============================================================

def main():
    analyze_baselines(BASELINES_CSV, FIGURES_DIR)

    if not INPUT_CSV.exists() or INPUT_CSV.stat().st_size == 0:
        raise FileNotFoundError(
            f"Missing experimental dataset: {INPUT_CSV}. Run measurements first."
        )

    # Carica e pulisci etichette
    raw_df = pd.read_csv(INPUT_CSV)
    df = clean_dataframe(raw_df)

    summary_df = compute_metrics(df)
    df = classify_speedup(df)

    plot_correctness(df, FIGURES_DIR)
    plot_speedup_distribution(df, FIGURES_DIR)
    plot_correctness_by_query(df, FIGURES_DIR)

    export_correctness_by_query(df, FIGURES_DIR)
    export_latex_table(summary_df, FIGURES_DIR)

    df.to_csv(FIGURES_DIR / "classified_measurements.csv", index=False)
    print("\n[SUCCESS] Tutti i grafici e tabelle rigenerati con grafica ad alta leggibilità!")


if __name__ == "__main__":
    main()