"""
cli.py - entry point of the measurement phase (run on the PostgreSQL machine).

Commands:
  python measure/cli.py env       --db tpch_sf01
      Save the PostgreSQL version and all settings (reproducibility).
  python measure/cli.py baseline  --db tpch_sf01 --queries queries/
      Time every input query and check that its three forms are equivalent.
  python measure/cli.py rewrites  --db tpch_sf01 --queries queries/ --generations results/generations.jsonl
      Check and time every LLM rewrite not measured yet (can be re-run any time).
  python measure/cli.py selftest  --db tpch_sf01
      Validate the pipeline on known cases (see selftest.py).

Options: --warmup W (1), --reps R (20), --timeout-s (60), --decimals (4), --out (results)

Pipeline for one rewrite (measure_one):
  sql_text (single statement?) -> db.run_query (runs?) -> compare (same result?)
  -> db.time_query (median) -> plans (plan changed?) -> io_files (measurements.csv)
"""

import argparse
import datetime as dt
import json
from pathlib import Path

from compare import compare_results
from db import classify_error, connect, run_query, stats, time_query
from io_files import (BASELINE_FIELDS, FORMS, MEASURE_FIELDS, append_csv,
                      load_generations, load_input_queries, now, read_csv,
                      rewrite_key, save_plan)
from plans import plan_hash, plan_signature
from sql_text import clean_sql, count_statements, has_top_level_order_by


def cmd_env(args):
    """Save PostgreSQL's version and every setting to results/env_<date>.json.

    Documents the exact environment of the measurements (C5) and avoids
    measuring on the wrong server version by mistake.
    """
    conn = connect(args.db, args.timeout_s)
    version = run_query(conn, "SELECT version()")[0][0]
    settings = run_query(conn, "SELECT name, setting, unit FROM pg_settings ORDER BY name")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"env_{dt.date.today().isoformat()}.json"
    with open(path, "w") as f:
        json.dump({"captured_at": now(), "db": args.db, "version": version,
                   "settings": {n: (s, u) for n, s, u in settings}}, f, indent=1)
    print(version)
    print(f"Saved {path}")


def ensure_baselines(conn, args, queries, out, wanted=None):
    """Time the input queries that are not in baselines.csv yet.

    The baseline of an input query is the reference time for the speedup of
    all its rewrites. Already measured baselines are reused (same database
    only). `wanted` limits the work to the queries actually needed.
    Returns {(query_id, form): baseline_row}.
    """
    path = out / "baselines.csv"
    done = {(r["query_id"], r["form"]): r for r in read_csv(path) if r["db"] == args.db}
    todo = [k for k in sorted(queries) if k not in done and (wanted is None or k in wanted)]
    for i, (qid, form) in enumerate(todo, 1):
        sql = clean_sql(queries[(qid, form)])
        print(f"[baseline {i}/{len(todo)}] {qid} {form} ...", end=" ", flush=True)
        try:
            rows = run_query(conn, sql)
            times, doc = time_query(conn, sql, args.warmup, args.reps)
        except Exception as e:
            # An input query should never fail: report it and continue.
            print(f"FAILED ({classify_error(e)}): {str(e).splitlines()[0]}")
            continue
        sig = plan_signature(doc["Plan"])
        save_plan(out, f"baseline_{args.db}_{qid}_{form}", doc, sig)
        row = {"query_id": qid, "form": form, "db": args.db,
               "warmup": args.warmup, "reps": args.reps, "rows": len(rows),
               "plan_hash": plan_hash(sig), "measured_at": now(), **stats(times)}
        append_csv(path, BASELINE_FIELDS, row)
        done[(qid, form)] = row
        print(f"median {row['median_ms']} ms, {len(rows)} rows")
    return done


def cmd_baseline(args):
    """Time every input query, then check that the 3 forms of each query agree.

    The second part validates Karina's variants: if a form is reported as
    DIFFERENT, it is not equivalent and must be fixed before the campaign,
    otherwise the comparison between forms would be meaningless.
    """
    conn = connect(args.db, args.timeout_s)
    queries = load_input_queries(args.queries)
    out = Path(args.out)
    base = ensure_baselines(conn, args, queries, out)

    print("\nEquivalence of the input forms:")
    by_q = {}
    for (qid, form) in queries:
        by_q.setdefault(qid, []).append(form)
    for qid in sorted(by_q):
        forms = sorted(by_q[qid], key=FORMS.index)
        ref_form = forms[0]                         # first available form is the reference
        ref_sql = clean_sql(queries[(qid, ref_form)])
        ref_rows = run_query(conn, ref_sql)
        ordered = has_top_level_order_by(ref_sql)
        verdicts = []
        for f in forms[1:]:
            try:
                ok, why = compare_results(ref_rows, run_query(conn, clean_sql(queries[(qid, f)])),
                                          ordered, args.decimals)
            except Exception as e:
                ok, why = False, classify_error(e)
            verdicts.append(f"{f}: {'same' if ok else 'DIFFERENT (' + why + ')'}")
        print(f"  {qid}: {ref_form} vs " + ", ".join(verdicts) if verdicts else f"  {qid}: only {ref_form}")
    print(f"\nBaselines in {out / 'baselines.csv'} ({len(base)} rows for {args.db})")


def measure_one(conn, args, gen, queries, base, ref_cache, out, timer=None):
    """Evaluate one LLM rewrite and return its row for measurements.csv.

    Steps (stop at the first failure, which is recorded in failure_type):
      0. text check: empty -> empty_sql, several statements -> multi_statement
         (never executed, so the database cannot be modified)
      1. execution: syntax_error / sql_error / timeout
      2. correctness: same result as the input query? else wrong_result
      3. timing (correct rewrites only): warm-up + R runs, median
      4. speedup = baseline median / rewrite median   (> 1 means faster)
         plan_changed = rewrite plan differs from the input query's plan
    """
    qid, form = str(gen["query_id"]), str(gen["form"])
    row = {"query_id": qid, "form": form, "model": gen["model"], "seed": gen["seed"],
           "temperature": gen.get("temperature", ""), "db": args.db,
           "warmup": args.warmup, "reps": args.reps, "measured_at": now(),
           "correct": False, "failure_type": "", "error": ""}

    # Reference result of the input form: computed once, reused for all its rewrites.
    if (qid, form) not in ref_cache:
        ref_sql = clean_sql(queries[(qid, form)])
        ref_cache[(qid, form)] = (run_query(conn, ref_sql), has_top_level_order_by(ref_sql))
    ref_rows, ordered = ref_cache[(qid, form)]

    # 0. Text check
    sql = clean_sql(gen.get("sql", ""))
    n_stmt = count_statements(sql)
    if n_stmt == 0:
        row["failure_type"] = "empty_sql"
        return row
    if n_stmt > 1:
        row["failure_type"] = "multi_statement"
        return row

    # 1. Execution
    try:
        cand_rows = run_query(conn, sql)
    except Exception as e:
        row["failure_type"] = classify_error(e)
        row["error"] = str(e).splitlines()[0][:200]
        return row

    # 2. Correctness
    row["rows"] = len(cand_rows)
    ok, why = compare_results(ref_rows, cand_rows, ordered, args.decimals)
    if not ok:
        # Logged but never timed: comparing the runtime of queries that
        # compute different results would be meaningless.
        row["failure_type"] = "wrong_result"
        row["error"] = why
        return row
    row["correct"] = True

    # 3. Timing
    try:
        times, doc = (timer or time_query)(conn, sql, args.warmup, args.reps)
    except Exception as e:
        row["failure_type"] = "timing_" + classify_error(e)   # correct but could not be timed
        row["error"] = str(e).splitlines()[0][:200]
        return row
    sig = plan_signature(doc["Plan"])
    save_plan(out, f"rw_{args.db}_{qid}_{form}_{gen['model']}_s{gen['seed']}_t{gen.get('temperature', '')}",
              doc, sig)
    s = stats(times)
    row.update({k: s[k] for k in ("median_ms", "mean_ms", "std_ms", "times_ms")})
    row["plan_hash"] = plan_hash(sig)

    # 4. Speedup and plan change, relative to the input query
    b = base.get((qid, form))
    if b:
        row["baseline_median_ms"] = b["median_ms"]
        row["baseline_plan_hash"] = b["plan_hash"]
        row["speedup"] = round(float(b["median_ms"]) / s["median_ms"], 4) if s["median_ms"] > 0 else ""
        row["plan_changed"] = row["plan_hash"] != b["plan_hash"]
    return row


def cmd_rewrites(args, gen_path=None):
    """Evaluate every rewrite of generations.jsonl that is not measured yet.

    Resumable: rewrites already in measurements.csv are skipped, so this can
    be re-run after each new batch of generations (git pull) or after a crash.
    Rewrites whose input query file is missing are reported and skipped.
    """
    conn = connect(args.db, args.timeout_s)
    queries = load_input_queries(args.queries)
    out = Path(args.out)
    gens = load_generations(gen_path or args.generations)
    path = out / "measurements.csv"
    done = {rewrite_key(r) for r in read_csv(path) if r["db"] == args.db}
    todo = [g for g in gens if rewrite_key(g) not in done]
    unknown = [g for g in todo if (str(g["query_id"]), str(g["form"])) not in queries]
    for g in unknown:
        print(f"  ! no input query for {g['query_id']} {g['form']}, skipped")
    todo = [g for g in todo if g not in unknown]
    print(f"{len(gens)} generations, {len(done)} already measured, {len(todo)} to do")

    wanted = {(str(g["query_id"]), str(g["form"])) for g in todo}
    base = ensure_baselines(conn, args, queries, out, wanted)   # baselines needed for the speedup
    ref_cache = {}
    for i, g in enumerate(todo, 1):
        label = f"{g['query_id']} {g['form']} {g['model']} seed={g['seed']} T={g.get('temperature', '')}"
        print(f"[{i}/{len(todo)}] {label} ...", end=" ", flush=True)
        row = measure_one(conn, args, g, queries, base, ref_cache, out)
        append_csv(path, MEASURE_FIELDS, row)       # written immediately (crash-safe)
        if row["correct"] and row.get("median_ms"):
            print(f"correct, median {row['median_ms']} ms, speedup {row.get('speedup', '?')}")
        else:
            print(f"{'correct but ' if row['correct'] else ''}{row['failure_type']} {row['error']}")
    print(f"Results in {path}")


def main():
    """Parse the command line and run the chosen command."""
    p = argparse.ArgumentParser(description="Correctness check and timing of SQL rewrites.")
    p.add_argument("command", choices=["env", "baseline", "rewrites", "selftest"])
    p.add_argument("--db", required=True, help="database name, e.g. tpch_sf01")
    p.add_argument("--queries", default="queries", help="folder with qXX_<form>.sql")
    p.add_argument("--generations", default="results/generations.jsonl")
    p.add_argument("--out", default="results")
    p.add_argument("--warmup", type=int, default=1, help="untimed runs before timing")
    p.add_argument("--reps", type=int, default=20, help="timed runs (median is kept)")
    p.add_argument("--timeout-s", type=float, default=60, help="per-query timeout in seconds")
    p.add_argument("--decimals", type=int, default=4, help="rounding for result comparison")
    args = p.parse_args()

    if args.command == "selftest":
        # Imported here: selftest needs cmd_baseline/cmd_rewrites from this file,
        # so a top-level import would be circular.
        from selftest import cmd_selftest
        cmd_selftest(args, cmd_baseline, cmd_rewrites)
    else:
        {"env": cmd_env, "baseline": cmd_baseline, "rewrites": cmd_rewrites}[args.command](args)


if __name__ == "__main__":
    main()