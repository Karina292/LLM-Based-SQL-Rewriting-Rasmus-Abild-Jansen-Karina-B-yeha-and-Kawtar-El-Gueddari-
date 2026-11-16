"""
Paired timing of the LLM rewrites (used for all the results in the paper).

The input query and the rewrite are run one after the other (input, rewrite,
input, ...) on a new connection for each rewrite, without prepared statements.
We do this because timing all baselines first and the rewrites later gave
biased speedups at SF 1 (see analysis/diag_timing.py).

Example:
  python measure/paired.py --db tpch_sf01_anon --queries results/queries_used
"""

import argparse
import statistics
from pathlib import Path

from cli import ensure_baselines, measure_one
from db import connect, explain_analyze, run_query
from io_files import (MEASURE_FIELDS, append_csv, load_generations,
                      load_input_queries, read_csv, rewrite_key)
from sql_text import clean_sql


def new_connection(args):
    """Open a fresh connection without automatic prepared statements."""
    conn = connect(args.db, args.timeout_s)
    conn.prepare_threshold = None
    return conn


def time_alternately(conn, input_sql, rewrite_sql, warmup, reps):
    """Time the input query and the rewrite in turn.

    Returns (input_times_ms, rewrite_times_ms, plan_of_last_rewrite_run).
    """
    for _ in range(warmup):                      # untimed warm-up of both
        run_query(conn, input_sql)
        run_query(conn, rewrite_sql)
    input_times, rewrite_times, plan = [], [], None
    for _ in range(reps):
        input_times.append(float(explain_analyze(conn, input_sql)["Execution Time"]))
        plan = explain_analyze(conn, rewrite_sql)
        rewrite_times.append(float(plan["Execution Time"]))
    return input_times, rewrite_times, plan


def main():
    p = argparse.ArgumentParser(description="Paired measurement of LLM rewrites.")
    p.add_argument("--db", required=True)
    p.add_argument("--queries", default="queries")
    p.add_argument("--generations", default="results/generations.jsonl")
    p.add_argument("--out", default="results")
    p.add_argument("--warmup", type=int, default=1)
    p.add_argument("--reps", type=int, default=20)
    p.add_argument("--timeout-s", type=float, default=60)
    p.add_argument("--decimals", type=int, default=4)
    args = p.parse_args()

    queries = load_input_queries(args.queries)
    out = Path(args.out)
    results_file = out / "measurements.csv"

    # Rewrites still to measure (resumable), grouped by input query.
    done = {rewrite_key(r) for r in read_csv(results_file) if r["db"] == args.db}
    todo = [g for g in load_generations(args.generations)
            if rewrite_key(g) not in done and (str(g["query_id"]), str(g["form"])) in queries]
    todo.sort(key=lambda g: (str(g["query_id"]), str(g["form"])))
    print(f"{len(todo)} rewrites to measure with paired timing on {args.db}")

    # Baselines are only needed here to detect plan changes.
    conn = new_connection(args)
    wanted = {(str(g["query_id"]), str(g["form"])) for g in todo}
    baselines = ensure_baselines(conn, args, queries, out, wanted)
    conn.close()

    ref_cache = {}
    for i, g in enumerate(todo, 1):
        input_sql = clean_sql(queries[(str(g["query_id"]), str(g["form"]))])
        input_times = []

        def paired_timer(conn, rewrite_sql, warmup, reps):
            """Timer given to measure_one: times input and rewrite alternately."""
            t_in, t_rw, plan = time_alternately(conn, input_sql, rewrite_sql, warmup, reps)
            input_times.extend(t_in)
            return t_rw, plan

        print(f"[{i}/{len(todo)}] {g['query_id']} {g['form']} {g['model']} seed={g['seed']} ...",
              end=" ", flush=True)
        conn = new_connection(args)
        row = measure_one(conn, args, g, queries, baselines, ref_cache, out, timer=paired_timer)
        conn.close()

        # Speedup from the interleaved runs (only for correct, timed rewrites).
        if input_times and row.get("median_ms"):
            row["baseline_median_ms"] = round(statistics.median(input_times), 3)
            row["speedup"] = round(row["baseline_median_ms"] / row["median_ms"], 4)

        append_csv(results_file, MEASURE_FIELDS, row)
        if row.get("median_ms"):
            print(f"correct, input {row['baseline_median_ms']} ms, rewrite {row['median_ms']} ms, "
                  f"speedup {row['speedup']}")
        else:
            print(row["failure_type"], row["error"])
    print(f"Results in {results_file}")


if __name__ == "__main__":
    main()
