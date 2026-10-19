#!/usr/bin/env python3
"""
measure.py - correctness check and timing of SQL rewrites on PostgreSQL.

Phase "measure" of the INF2204 pipeline (runs on the PostgreSQL machine).

Commands
--------
  python measure.py env       --db tpch_sf01
      Save PostgreSQL version and settings to results/env_<date>.json.

  python measure.py baseline  --db tpch_sf01 --queries queries/
      Time every input form (queries/qXX_nested.sql, qXX_join.sql, qXX_cte.sql).
      Output: results/baselines.csv

  python measure.py rewrites  --db tpch_sf01 --queries queries/ \
                              --generations results/generations.jsonl
      For every generated rewrite not yet measured:
        1. run it and compare its result with the input form's result
        2. if correct: W warm-up runs + R timed runs, keep the median
      Output: results/measurements.csv (+ results/plans/*.json)

  python measure.py selftest  --db tpch_sf01
      End-to-end test with a hand-written query (TPC-H Q4) in 3 forms and
      4 fake rewrites whose expected verdicts are known. Writes to
      selftest/ and prints PASS/FAIL. No LLM needed.

Common options: --warmup W (default 1), --reps R (default 20),
                --timeout-s (default 60), --decimals (default 4), --out results

Correctness rule
----------------
A rewrite is correct iff it returns exactly the same multiset of rows as the
input query (same row count, no row missing on either side, i.e. both
EXCEPT ALL directions empty). If the input query has a top-level ORDER BY,
the order must match too. Numeric values are rounded to --decimals digits
before comparison so that equivalent arithmetic is not counted as a mismatch.

Failure types: empty_sql, multi_statement, syntax_error, sql_error,
               timeout, wrong_result
"""

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import re
import statistics
import sys
from decimal import Decimal
from pathlib import Path

try:
    import psycopg
    from psycopg import errors as pgerr
except ImportError:  # allows importing the pure functions without psycopg
    psycopg = None
    pgerr = None

FORMS = ("nested", "join", "cte")

BASELINE_FIELDS = [
    "query_id", "form", "db", "warmup", "reps", "rows",
    "median_ms", "mean_ms", "std_ms", "min_ms", "max_ms",
    "plan_hash", "times_ms", "measured_at",
]
MEASURE_FIELDS = [
    "query_id", "form", "model", "seed", "temperature", "db",
    "correct", "failure_type", "error", "rows",
    "warmup", "reps", "median_ms", "mean_ms", "std_ms",
    "baseline_median_ms", "speedup", "plan_hash", "baseline_plan_hash",
    "plan_changed", "times_ms", "measured_at",
]


# --------------------------------------------------------------------------
# SQL text helpers (no external parser needed)
# --------------------------------------------------------------------------

def _scan(sql):
    """Yield (index, char, depth) for characters outside strings/comments."""
    depth = 0
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if c == "'":                       # string literal ('' escapes)
            i += 1
            while i < n:
                if sql[i] == "'" and i + 1 < n and sql[i + 1] == "'":
                    i += 2
                    continue
                if sql[i] == "'":
                    break
                i += 1
        elif c == '"':                     # quoted identifier
            i += 1
            while i < n and sql[i] != '"':
                i += 1
        elif sql.startswith("--", i):      # line comment
            while i < n and sql[i] != "\n":
                i += 1
        elif sql.startswith("/*", i):      # block comment
            j = sql.find("*/", i + 2)
            i = n if j < 0 else j + 1
        else:
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            yield i, c, depth
        i += 1


def clean_sql(sql):
    """Strip whitespace and trailing semicolons."""
    s = (sql or "").strip()
    while s.endswith(";"):
        s = s[:-1].rstrip()
    return s


def count_statements(sql):
    """Number of statements separated by top-level semicolons."""
    s = clean_sql(sql)
    if not s:
        return 0
    parts, start = [], 0
    for i, c, depth in _scan(s):
        if c == ";" and depth == 0:
            parts.append(s[start:i])
            start = i + 1
    parts.append(s[start:])
    return sum(1 for p in parts if p.strip())


def has_top_level_order_by(sql):
    """True if the outermost query ends with ORDER BY (not inside parentheses)."""
    s = clean_sql(sql)
    top = "".join(c if depth == 0 and c != ")" else " " for _, c, depth in _scan(s))
    return re.search(r"\border\s+by\b", top, re.IGNORECASE) is not None


# --------------------------------------------------------------------------
# Result comparison
# --------------------------------------------------------------------------

def _norm_value(v, decimals):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, Decimal):
        return round(float(v), decimals)
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        return round(v, decimals)
    if isinstance(v, int):
        return float(v)                   # 3 and 3.0 compare equal
    if isinstance(v, str):
        return v.rstrip()                 # char(n) padding
    return str(v)                         # dates, intervals, ...


def normalize_rows(rows, decimals):
    return [tuple(_norm_value(v, decimals) for v in r) for r in rows]


def _sort_key(row):
    return tuple((v is None, str(type(v)), v if v is not None else 0) for v in row)


def compare_results(ref_rows, cand_rows, ordered, decimals):
    """Return (equal: bool, reason: str)."""
    a = normalize_rows(ref_rows, decimals)
    b = normalize_rows(cand_rows, decimals)
    if len(a) != len(b):
        return False, f"row count {len(b)} != {len(a)}"
    if a and b and len(a[0]) != len(b[0]):
        return False, f"column count {len(b[0])} != {len(a[0])}"
    if ordered:
        if a == b:
            return True, ""
        same_set = sorted(a, key=_sort_key) == sorted(b, key=_sort_key)
        return False, "same rows, different order" if same_set else "different rows"
    if sorted(a, key=_sort_key) == sorted(b, key=_sort_key):
        return True, ""
    return False, "different rows"


# --------------------------------------------------------------------------
# Plans
# --------------------------------------------------------------------------

def plan_signature(plan):
    """Pre-order list of operators, e.g. 'Sort>Hash Join[Inner]>Seq Scan(orders)>...'."""
    parts = []

    def walk(node):
        label = node.get("Node Type", "?")
        if node.get("Join Type"):
            label += f"[{node['Join Type']}]"
        if node.get("Strategy"):
            label += f"{{{node['Strategy']}}}"
        if node.get("Relation Name"):
            label += f"({node['Relation Name']})"
        parts.append(label)
        for child in node.get("Plans", []) or []:
            walk(child)

    walk(plan)
    return ">".join(parts)


def plan_hash(signature):
    return hashlib.sha1(signature.encode()).hexdigest()[:10]


# --------------------------------------------------------------------------
# Database access
# --------------------------------------------------------------------------

def connect(db, timeout_s):
    if psycopg is None:
        sys.exit("psycopg is not installed: pip install 'psycopg[binary]'")
    conn = psycopg.connect(dbname=db, autocommit=True)
    conn.execute(f"SET statement_timeout = {int(timeout_s * 1000)}")
    return conn


def run_query(conn, sql):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall() if cur.description else []


def explain_analyze(conn, sql):
    with conn.cursor() as cur:
        cur.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql)
        doc = cur.fetchone()[0]
    if isinstance(doc, str):
        doc = json.loads(doc)
    return doc[0]                          # {"Plan": ..., "Execution Time": ...}


def classify_error(exc):
    if pgerr is not None and isinstance(exc, pgerr.QueryCanceled):
        return "timeout"
    if pgerr is not None and isinstance(exc, pgerr.SyntaxError):
        return "syntax_error"
    return "sql_error"


def time_query(conn, sql, warmup, reps):
    """Warm-up runs, then R EXPLAIN ANALYZE runs. Returns (times_ms, last_plan_doc)."""
    for _ in range(warmup):
        run_query(conn, sql)
    times, doc = [], None
    for _ in range(reps):
        doc = explain_analyze(conn, sql)
        times.append(float(doc["Execution Time"]))
    return times, doc


def stats(times):
    return {
        "median_ms": round(statistics.median(times), 3),
        "mean_ms": round(statistics.fmean(times), 3),
        "std_ms": round(statistics.stdev(times), 3) if len(times) > 1 else 0.0,
        "min_ms": round(min(times), 3),
        "max_ms": round(max(times), 3),
        "times_ms": ";".join(f"{t:.3f}" for t in times),
    }


# --------------------------------------------------------------------------
# Files
# --------------------------------------------------------------------------

def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def read_csv(path):
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def append_csv(path, fields, row):
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)
        f.flush()
        os.fsync(f.fileno())


def load_input_queries(qdir):
    """{(query_id, form): sql} from files named <query_id>_<form>.sql."""
    out = {}
    for p in sorted(Path(qdir).glob("*.sql")):
        m = re.match(r"(.+)_(nested|join|cte)$", p.stem)
        if m:
            out[(m.group(1), m.group(2))] = p.read_text()
    if not out:
        sys.exit(f"No files like q04_nested.sql found in {qdir}")
    return out


def load_generations(path):
    rows = []
    with open(path) as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"  ! line {n} of {path} is not valid JSON, skipped")
    return rows


def rewrite_key(r):
    return (str(r["query_id"]), str(r["form"]), str(r["model"]),
            str(r["seed"]), str(r.get("temperature", "")))


def save_plan(out, name, doc, signature):
    pdir = out / "plans"
    pdir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    with open(pdir / f"{safe}.json", "w") as f:
        json.dump({"signature": signature, "explain": doc}, f, indent=1, default=str)


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def cmd_env(args):
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
    """Measure missing baselines; return {(query_id, form): row}."""
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
    conn = connect(args.db, args.timeout_s)
    queries = load_input_queries(args.queries)
    out = Path(args.out)
    base = ensure_baselines(conn, args, queries, out)

    # Check that the three forms of each query return the same result.
    print("\nEquivalence of the input forms:")
    by_q = {}
    for (qid, form) in queries:
        by_q.setdefault(qid, []).append(form)
    for qid in sorted(by_q):
        forms = sorted(by_q[qid], key=FORMS.index)
        ref_form = forms[0]
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


def measure_one(conn, args, gen, queries, base, ref_cache, out):
    qid, form = str(gen["query_id"]), str(gen["form"])
    row = {"query_id": qid, "form": form, "model": gen["model"], "seed": gen["seed"],
           "temperature": gen.get("temperature", ""), "db": args.db,
           "warmup": args.warmup, "reps": args.reps, "measured_at": now(),
           "correct": False, "failure_type": "", "error": ""}

    # Reference result of the input form (cached).
    if (qid, form) not in ref_cache:
        ref_sql = clean_sql(queries[(qid, form)])
        ref_cache[(qid, form)] = (run_query(conn, ref_sql), has_top_level_order_by(ref_sql))
    ref_rows, ordered = ref_cache[(qid, form)]

    sql = clean_sql(gen.get("sql", ""))
    n_stmt = count_statements(sql)
    if n_stmt == 0:
        row["failure_type"] = "empty_sql"
        return row
    if n_stmt > 1:
        row["failure_type"] = "multi_statement"
        return row

    # 1. Correctness
    try:
        cand_rows = run_query(conn, sql)
    except Exception as e:
        row["failure_type"] = classify_error(e)
        row["error"] = str(e).splitlines()[0][:200]
        return row
    row["rows"] = len(cand_rows)
    ok, why = compare_results(ref_rows, cand_rows, ordered, args.decimals)
    if not ok:
        row["failure_type"] = "wrong_result"
        row["error"] = why
        return row
    row["correct"] = True

    # 2. Timing (only correct rewrites)
    try:
        times, doc = time_query(conn, sql, args.warmup, args.reps)
    except Exception as e:  # e.g. timeout during timing runs
        row["correct"] = True
        row["failure_type"] = "timing_" + classify_error(e)
        row["error"] = str(e).splitlines()[0][:200]
        return row
    sig = plan_signature(doc["Plan"])
    save_plan(out, f"rw_{args.db}_{qid}_{form}_{gen['model']}_s{gen['seed']}_t{gen.get('temperature', '')}",
              doc, sig)
    s = stats(times)
    b = base.get((qid, form))
    row.update({k: s[k] for k in ("median_ms", "mean_ms", "std_ms", "times_ms")})
    row["plan_hash"] = plan_hash(sig)
    if b:
        row["baseline_median_ms"] = b["median_ms"]
        row["baseline_plan_hash"] = b["plan_hash"]
        row["speedup"] = round(float(b["median_ms"]) / s["median_ms"], 4) if s["median_ms"] > 0 else ""
        row["plan_changed"] = row["plan_hash"] != b["plan_hash"]
    return row


def cmd_rewrites(args, gen_path=None):
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
    base = ensure_baselines(conn, args, queries, out, wanted)
    ref_cache = {}
    for i, g in enumerate(todo, 1):
        label = f"{g['query_id']} {g['form']} {g['model']} seed={g['seed']} T={g.get('temperature', '')}"
        print(f"[{i}/{len(todo)}] {label} ...", end=" ", flush=True)
        row = measure_one(conn, args, g, queries, base, ref_cache, out)
        append_csv(path, MEASURE_FIELDS, row)
        if row["correct"] and row.get("median_ms"):
            print(f"correct, median {row['median_ms']} ms, speedup {row.get('speedup', '?')}")
        else:
            print(f"{'correct but ' if row['correct'] else ''}{row['failure_type']} {row['error']}")
    print(f"Results in {path}")


# --------------------------------------------------------------------------
# Self-test (TPC-H Q4, hand-written forms)
# --------------------------------------------------------------------------

Q4_WHERE = ("o_orderdate >= date '1993-07-01' "
            "and o_orderdate < date '1993-07-01' + interval '3' month")

SELFTEST_FORMS = {
    "nested": f"""
select o_orderpriority, count(*) as order_count
from orders
where {Q4_WHERE}
  and exists (select * from lineitem
              where l_orderkey = o_orderkey and l_commitdate < l_receiptdate)
group by o_orderpriority
order by o_orderpriority;
""",
    "join": f"""
select o_orderpriority, count(distinct o_orderkey) as order_count
from orders join lineitem on l_orderkey = o_orderkey
where {Q4_WHERE}
  and l_commitdate < l_receiptdate
group by o_orderpriority
order by o_orderpriority;
""",
    "cte": f"""
with late_orders as (
  select distinct l_orderkey from lineitem where l_commitdate < l_receiptdate
)
select o_orderpriority, count(*) as order_count
from orders join late_orders on late_orders.l_orderkey = o_orderkey
where {Q4_WHERE}
group by o_orderpriority
order by o_orderpriority;
""",
}

# (fake rewrite of the nested form, expected verdict)
SELFTEST_REWRITES = [
    (SELFTEST_FORMS["join"], "correct"),
    (SELFTEST_FORMS["cte"], "correct"),
    (SELFTEST_FORMS["join"].replace("1993-07-01", "1993-10-01"), "wrong_result"),
    ("selec o_orderpriority from orders", "syntax_error"),
    (SELFTEST_FORMS["join"].replace("order by o_orderpriority", "order by o_orderpriority desc"),
     "wrong_result"),
    ("select 1; select 2", "multi_statement"),
]


def cmd_selftest(args):
    root = Path("selftest")
    qdir, out = root / "queries", root / "results"
    qdir.mkdir(parents=True, exist_ok=True)
    for f in ("measurements.csv", "baselines.csv"):
        (out / f).unlink(missing_ok=True)
    for form, sql in SELFTEST_FORMS.items():
        (qdir / f"q04_{form}.sql").write_text(sql.strip() + "\n")
    gen_path = root / "generations.jsonl"
    with open(gen_path, "w") as f:
        for seed, (sql, _) in enumerate(SELFTEST_REWRITES):
            f.write(json.dumps({"query_id": "q04", "form": "nested", "model": "selftest",
                                "seed": seed, "temperature": 0.0, "sql": sql}) + "\n")
    args.queries, args.out = str(qdir), str(out)
    args.reps = min(args.reps, 5)
    cmd_baseline(args)
    print()
    cmd_rewrites(args, gen_path)

    rows = read_csv(out / "measurements.csv")
    print("\nSelf-test verdicts:")
    all_ok = True
    for r, (_, expected) in zip(rows, SELFTEST_REWRITES):
        got = "correct" if r["correct"] == "True" and not r["failure_type"] else r["failure_type"]
        ok = got == expected
        all_ok &= ok
        print(f"  seed {r['seed']}: expected {expected:15s} got {got:15s} {'PASS' if ok else 'FAIL'}")
    timed = [r for r in rows if r["median_ms"]]
    if timed and not all(r["speedup"] for r in timed):
        all_ok = False
        print("  speedup missing for a timed rewrite: FAIL")
    print("\nSELF-TEST", "PASSED" if all_ok and len(rows) == len(SELFTEST_REWRITES) else "FAILED")


# --------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Correctness check and timing of SQL rewrites.")
    p.add_argument("command", choices=["env", "baseline", "rewrites", "selftest"])
    p.add_argument("--db", required=True, help="database name, e.g. tpch_sf01")
    p.add_argument("--queries", default="queries", help="folder with qXX_<form>.sql")
    p.add_argument("--generations", default="results/generations.jsonl")
    p.add_argument("--out", default="results")
    p.add_argument("--warmup", type=int, default=1)
    p.add_argument("--reps", type=int, default=20)
    p.add_argument("--timeout-s", type=float, default=60)
    p.add_argument("--decimals", type=int, default=4)
    args = p.parse_args()
    {"env": cmd_env, "baseline": cmd_baseline,
     "rewrites": cmd_rewrites, "selftest": cmd_selftest}[args.command](args)


if __name__ == "__main__":
    main()
