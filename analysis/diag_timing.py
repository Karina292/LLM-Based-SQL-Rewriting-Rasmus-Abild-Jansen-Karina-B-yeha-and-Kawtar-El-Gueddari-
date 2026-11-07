"""
diag_timing.py - checks that speedups are not measurement artifacts.

These are the diagnostics that led us to the paired protocol at SF 1
(measure/paired.py; see the Pilot Experiments section of the paper).

Run from the repository root:
  python analysis/diag_timing.py                    # checks 1 and 2 on SF 1
  python analysis/diag_timing.py --prepare          # also check 3
  python analysis/diag_timing.py --db tpch_sf01_anon

Check 1 - same-plan rewrites
  A rewrite with exactly the same plan as its input query does the same work,
  so its speedup should be about 1.0. A median far from 1.0 means the timing,
  not the rewrite, is biased.

Check 2 - alternating test
  For the 3 same-plan rewrites with the lowest stored speedup, time the input
  query and the rewrite in turn (A, B, A, B, ...) on a fresh connection.
  If they now take the same time, the stored speedup was an artifact.

Check 3 - prepared statements (--prepare)
  psycopg automatically prepares a query run more than 5 times on the same
  connection. Time the same pairs with and without this feature to see whether
  it changes execution times.
"""

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, "measure")
from db import connect, explain_analyze
from sql_text import clean_sql

REPS = 10      # runs of each query in checks 2 and 3


def rewrite_id(r):
    return (str(r["query_id"]), str(r["form"]), str(r["model"]), str(r["seed"]))


def load_data(db):
    """Input queries, generated rewrites, and timed same-plan rewrites of `db`."""
    queries = {}
    for path in Path("queries").glob("q*_*.sql"):
        query_id, form = path.stem.split("_", 1)
        queries[(query_id, form)] = path.read_text()
    rewrites = {}
    for line in open("results/generations.jsonl"):
        if line.strip():
            g = json.loads(line)
            rewrites[rewrite_id(g)] = g["sql"]
    same_plan = [r for r in csv.DictReader(open("results/measurements.csv"))
                 if r["db"] == db and r["speedup"] and r["plan_changed"] == "False"]
    return queries, rewrites, same_plan


def check_same_plan(same_plan):
    print("Check 1 - median speedup of same-plan rewrites (should be about 1.0)")
    for query_id in sorted({r["query_id"] for r in same_plan}):
        s = [float(r["speedup"]) for r in same_plan if r["query_id"] == query_id]
        print(f"  {query_id}: {statistics.median(s):.2f}  (n = {len(s)})")


def worst_cases(same_plan, n=3):
    """The n same-plan rewrites with the lowest speedup, one per query."""
    chosen, seen = [], set()
    for r in sorted(same_plan, key=lambda r: float(r["speedup"])):
        if r["query_id"] not in seen:
            chosen.append(r)
            seen.add(r["query_id"])
    return chosen[:n]


def time_pair(db, input_sql, rewrite_sql, prepare=True, preruns=0):
    """Median times (ms) of input and rewrite, timed in turn on a fresh connection."""
    conn = connect(db, 120)
    if not prepare:
        conn.prepare_threshold = None            # disable automatic prepared statements
    for _ in range(preruns):                     # optionally run the input many times first
        explain_analyze(conn, input_sql)
    explain_analyze(conn, input_sql)             # warm-up of both
    explain_analyze(conn, rewrite_sql)
    t_input, t_rewrite = [], []
    for _ in range(REPS):
        t_input.append(explain_analyze(conn, input_sql)["Execution Time"])
        t_rewrite.append(explain_analyze(conn, rewrite_sql)["Execution Time"])
    conn.close()
    return statistics.median(t_input), statistics.median(t_rewrite)


def main():
    p = argparse.ArgumentParser(description="Timing diagnostics.")
    p.add_argument("--db", default="tpch_sf1_anon")
    p.add_argument("--prepare", action="store_true", help="also run check 3")
    args = p.parse_args()

    queries, rewrites, same_plan = load_data(args.db)
    check_same_plan(same_plan)

    cases = [(r, clean_sql(queries[(r["query_id"], r["form"])]), clean_sql(rewrites[rewrite_id(r)]))
             for r in worst_cases(same_plan)]

    print(f"\nCheck 2 - alternating test ({REPS} runs each, fresh connection)")
    for r, input_sql, rewrite_sql in cases:
        t_in, t_rw = time_pair(args.db, input_sql, rewrite_sql)
        print(f"  {r['query_id']} {r['form']:6s}: stored speedup {float(r['speedup']):.2f}, "
              f"now input {t_in:.1f} ms, rewrite {t_rw:.1f} ms -> speedup {t_in / t_rw:.2f}")

    if args.prepare:
        print("\nCheck 3 - with and without automatic prepared statements "
              "(input run 25 times first)")
        for r, input_sql, rewrite_sql in cases:
            on = time_pair(args.db, input_sql, rewrite_sql, prepare=True, preruns=25)
            off = time_pair(args.db, input_sql, rewrite_sql, prepare=False, preruns=25)
            print(f"  {r['query_id']} {r['form']:6s}: prepare ON  input {on[0]:.1f} ms, rewrite {on[1]:.1f} ms"
                  f" | prepare OFF input {off[0]:.1f} ms, rewrite {off[1]:.1f} ms")


if __name__ == "__main__":
    main()
