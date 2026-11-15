#!/usr/bin/env python3
"""Break-even k* for LLM rewrites.

k* = T_gen / (T_base - T_rewrite): how many executions a rewrite needs before
the one-off generation cost is paid back.

Only correct rewrites with speedup > threshold (default 1.05) get a k*.
T_gen      = gen_time_ms from generations.jsonl (prompt_eval + eval, load excluded)
T_base     = baseline_median_ms in measurements.csv (same-session baseline)
T_rewrite  = median_ms in measurements.csv

Usage:
    python breakeven/breakeven.py --measurements results/measurements.csv \
        --generations results/generations.jsonl --out results/breakeven
Rerun with the SF 1 measurements file to get SF 1 numbers.
"""
import argparse
import json
from pathlib import Path

import pandas as pd

def db_label(db):
    if db.endswith("_idx"):
        return "FK idx"
    if db.endswith("_anon"):
        return "no idx"
    return db


def load(meas_path, gen_path):
    m = pd.read_csv(meas_path)
    g = pd.DataFrame(json.loads(l) for l in open(gen_path, encoding="utf-8") if l.strip())
    g = g[["query_id", "form", "model", "seed", "gen_time_ms", "output_tokens"]]
    return m, g


def compute(m, g, threshold):
    m = m.copy()
    m["correct"] = m["correct"].astype(str).str.lower() == "true"
    c = m[m.correct & (m.speedup > threshold)]
    c = c.merge(g, on=["query_id", "form", "model", "seed"], how="left", validate="m:1")
    missing = c.gen_time_ms.isna().sum()
    if missing:
        raise SystemExit(f"{missing} measured rewrites have no generation record")
    c["saved_ms"] = c.baseline_median_ms - c.median_ms
    c["k_star"] = c.gen_time_ms / c.saved_ms
    c["model"] = c.model.str.split(":").str[0]
    cols = ["db", "query_id", "form", "model", "seed", "baseline_median_ms", "median_ms",
            "speedup", "saved_ms", "gen_time_ms", "k_star", "plan_changed"]
    return c[cols].sort_values(["db", "k_star"]).reset_index(drop=True)


def summarize(rows):
    s = (rows.groupby(["db", "query_id", "model", "form"])
         .agg(n=("seed", "size"), speedup=("speedup", "median"), saved_ms=("saved_ms", "median"),
              t_gen_ms=("gen_time_ms", "median"), k_star=("k_star", "median"),
              k_star_min=("k_star", "min"))
         .reset_index().sort_values(["db", "k_star"]))
    return s


def gen_cost(g, m, rows, threshold):
    """Per-model generation cost plus k* distribution per database."""
    g = g.copy()
    g["model"] = g.model.str.split(":").str[0]
    out = []
    for model, gg in g.groupby("model"):
        r = {"model": model, "n_gen": len(gg),
             "t_gen_med_s": gg.gen_time_ms.median() / 1000,
             "t_gen_q1_s": gg.gen_time_ms.quantile(.25) / 1000,
             "t_gen_q3_s": gg.gen_time_ms.quantile(.75) / 1000,
             "tokens_med": gg.output_tokens.median()}
        for db in sorted(rows.db.unique()):
            rr = rows[(rows.model == model) & (rows.db == db)]
            r[f"n_fast_{db}"] = len(rr)
            r[f"k_med_{db}"] = rr.k_star.median() if len(rr) else float("nan")
            r[f"k_min_{db}"] = rr.k_star.min() if len(rr) else float("nan")
        out.append(r)
    return pd.DataFrame(out)


def fmt_k(x):
    if pd.isna(x):
        return "--"
    if x < 10:
        return f"{x:.1f}"
    return f"{x:,.0f}".replace(",", "{,}")


def latex(cost, dbs, threshold, n_total):
    pretty = {"qwen2.5-coder": "Qwen2.5-Coder 7B", "llama3.1": "Llama 3.1 8B"}
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\footnotesize",
        r"\begin{adjustbox}{max width=\columnwidth}",
        r"\begin{tabular}{l r r " + " ".join(["r r r"] * len(dbs)) + "}",
    ]
    caption = (r"\caption{Generation cost and break-even point $k^* = T_\text{gen}/(T_\text{base}-T_\text{rewrite})$. "
        r"$T_\text{gen}$ is prompt evaluation plus decoding (model load excluded), median and IQR over all "
        f"{n_total} generations per model. $k^*$ is computed only for correct rewrites with speedup "
        f"$>{threshold}$; $n$ is the number of such rewrites (out of 225 per model and database). "
        r"Computed with \texttt{breakeven.py} in our repository.}")
    lines += [
        r"\toprule",
        " & & & " + " & ".join(
            rf"\multicolumn{{3}}{{c}}{{{db_label(d)}}}" for d in dbs) + r" \\",
        "".join(rf"\cmidrule(lr){{{4 + 3 * i}-{6 + 3 * i}}}" for i in range(len(dbs))),
        r"Model & $T_\text{gen}$ (s) & Tokens & " + " & ".join(
            [r"$n$ & min $k^*$ & med.\ $k^*$"] * len(dbs)) + r" \\",
        r"\midrule",
    ]
    for _, r in cost.iterrows():
        cells = [pretty.get(r.model, r.model),
                 f"{r.t_gen_med_s:.1f} [{r.t_gen_q1_s:.1f}, {r.t_gen_q3_s:.1f}]",
                 f"{r.tokens_med:.0f}"]
        for d in dbs:
            cells += [str(int(r[f'n_fast_{d}'])), fmt_k(r[f"k_min_{d}"]), fmt_k(r[f"k_med_{d}"])]
        lines.append(" & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{adjustbox}",
              caption, r"\label{tab:gencost}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measurements", default="results/measurements.csv")
    ap.add_argument("--generations", default="results/generations.jsonl")
    ap.add_argument("--out", default="results/breakeven")
    ap.add_argument("--threshold", type=float, default=1.05)
    a = ap.parse_args()

    m, g = load(a.measurements, a.generations)
    rows = compute(m, g, a.threshold)
    summ = summarize(rows)
    dbs = sorted(rows.db.unique())
    cost = gen_cost(g, m, rows, a.threshold)
    n_total = int(g.groupby("model").size().max())

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows.to_csv(out / "breakeven_rows.csv", index=False, float_format="%.3f")
    summ.to_csv(out / "breakeven_summary.csv", index=False, float_format="%.3f")
    cost.to_csv(out / "gencost.csv", index=False, float_format="%.3f")
    (out / "gencost_table.tex").write_text(latex(cost, dbs, a.threshold, n_total), encoding="utf-8")

    pd.set_option("display.width", 200)
    print(summ.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    print()
    print(cost.to_string(index=False, float_format=lambda x: f"{x:.1f}"))
    print(f"\nWrote {out}/breakeven_rows.csv, breakeven_summary.csv, gencost.csv, gencost_table.tex")


if __name__ == "__main__":
    main()
