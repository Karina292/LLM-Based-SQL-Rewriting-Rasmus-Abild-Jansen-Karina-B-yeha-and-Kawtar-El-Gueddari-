"""
pilot_temperature.py - temperature pilot (C16): is T = 0.7 a good choice?

Held-out queries (not in the main study): q14, q16, q22. Both models, T in
{0.2, 0.4, 0.7, 1.0}, seeds 1-5. For each (model, T) we report the share of
correct rewrites and the number of distinct rewrites. Decision rule (schedule):
the highest T whose correctness stays close to the lowest T, so that the
5 runs still differ.

Steps (run in this order, on Rasmus' PC):
  python pilots/pilot_temperature.py data       TPC-H SF 0.1 -> CSV (DuckDB's dbgen), pilot_data/
  python pilots/pilot_temperature.py db         create the PostgreSQL database tpch_pilot
                                         (schema_anon.sql + anonymize_values.sql)
  python pilots/pilot_temperature.py queries    anonymize q14, q16, q22 -> results/pilots/queries/
  python pilots/pilot_temperature.py generate   120 rewrites -> results/pilots/temperature_generations.jsonl
  python pilots/pilot_temperature.py check      correctness + distinct rewrites -> results/pilots/

The connection uses libpq's defaults, like measure/db.py (psycopg.connect(dbname=...)):
  - in WSL / on Linux: the local socket as your own user, no password
    (create the role once: sudo -u postgres createuser -s $USER);
  - on Windows: set PGUSER=postgres and PGHOST=localhost, and put the password in
    %APPDATA%\\postgresql\\pgpass.conf (line   localhost:5432:*:postgres:<password>).
'generate' needs Ollama, so run it on Windows; data, db and check can run where
PostgreSQL is. The database is only used for correctness (same result rows), not timing.
"""

import argparse
import csv
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "generate"))  # generate.py, run_logger.py live in generate/
import generate as g
import run_logger as rl

sys.path.insert(0, str(rl.ROOT / "measure"))
from compare import compare_results
from sql_text import clean_sql, count_statements, has_top_level_order_by

DB = "tpch_pilot"
QUERIES = ("q14", "q16", "q22")
TEMPERATURES = (0.2, 0.4, 0.7, 1.0)
FORM = "orig"                                    # held-out queries have only their original form
DATA = rl.ROOT / "pilot_data"
PILOTS = rl.RESULTS / "pilots"
GENERATIONS = PILOTS / "temperature_generations.jsonl"

# TPC-H table -> (anonymized table, columns in TPC-H order). The anonymized columns
# of schema_anon.sql are in the same order, so the renaming is read from there.
TPCH = {
    "region":   ("tbl_zones",          ["r_regionkey", "r_name", "r_comment"]),
    "nation":   ("tbl_countries",      ["n_nationkey", "n_name", "n_regionkey", "n_comment"]),
    "supplier": ("tbl_suppliers",      ["s_suppkey", "s_name", "s_address", "s_nationkey", "s_phone",
                                        "s_acctbal", "s_comment"]),
    "customer": ("tbl_customers",      ["c_custkey", "c_name", "c_address", "c_nationkey", "c_phone",
                                        "c_acctbal", "c_mktsegment", "c_comment"]),
    "part":     ("tbl_parts",          ["p_partkey", "p_name", "p_mfgr", "p_brand", "p_type", "p_size",
                                        "p_container", "p_retailprice", "p_comment"]),
    "partsupp": ("tbl_part_suppliers", ["ps_partkey", "ps_suppkey", "ps_availqty", "ps_supplycost",
                                        "ps_comment"]),
    "orders":   ("tbl_orders",         ["o_orderkey", "o_custkey", "o_orderstatus", "o_totalprice",
                                        "o_orderdate", "o_orderpriority", "o_clerk", "o_shippriority",
                                        "o_comment"]),
    "lineitem": ("tbl_items",          ["l_orderkey", "l_partkey", "l_suppkey", "l_linenumber",
                                        "l_quantity", "l_extendedprice", "l_discount", "l_tax",
                                        "l_returnflag", "l_linestatus", "l_shipdate", "l_commitdate",
                                        "l_receiptdate", "l_shipinstruct", "l_shipmode", "l_comment"]),
}


def connect(dbname, autocommit=True):
    """Connect to PostgreSQL with libpq's defaults (same as measure/db.py)."""
    import psycopg
    try:
        conn = psycopg.connect(dbname=dbname, autocommit=autocommit)
    except psycopg.OperationalError as e:
        sys.exit(f"Cannot connect to {dbname}: {str(e).strip()}\n"
                 "WSL/Linux: create your role once with  sudo -u postgres createuser -s $USER\n"
                 "Windows: set PGUSER=postgres and PGHOST=localhost, and use pgpass.conf for the password\n"
                 "(the password stays on your PC; do not paste it in the chat).")
    return conn


# --- data ------------------------------------------------------------------

def cmd_data(args):
    """Generate TPC-H at SF 0.1 with DuckDB's dbgen and write one CSV per table."""
    import duckdb
    con = duckdb.connect()
    try:
        con.execute(f"CALL dbgen(sf={args.sf})")
    except duckdb.Error:                 # tpch extension not bundled: load it (one-time download)
        con.execute("INSTALL tpch; LOAD tpch;")
        con.execute(f"CALL dbgen(sf={args.sf})")
    DATA.mkdir(exist_ok=True)
    for table in TPCH:
        path = (DATA / f"{table}.csv").as_posix()
        con.execute(f"COPY {table} TO '{path}' (FORMAT csv, HEADER false)")
        print(f"  {table}: {con.execute(f'select count(*) from {table}').fetchone()[0]} rows")
    print(f"Saved in {DATA}")


# --- database --------------------------------------------------------------

def cmd_db(args):
    """(Re)create the database tpch_pilot with the anonymized schema and data."""
    if not all((DATA / f"{t}.csv").exists() for t in TPCH):
        sys.exit("Run 'python pilots/pilot_temperature.py data' first.")
    admin = connect("postgres")
    admin.execute(f'DROP DATABASE IF EXISTS "{DB}"')
    admin.execute(f'CREATE DATABASE "{DB}"')
    admin.close()

    conn = connect(DB)
    conn.execute((rl.ROOT / "queries" / "schema_anon.sql").read_text(encoding="utf-8"))
    # foreign keys: load parents first (dict order is already parents before children)
    for table, (anon, _) in TPCH.items():
        with conn.cursor() as cur, open(DATA / f"{table}.csv", "rb") as f, \
                cur.copy(f"COPY {anon} FROM STDIN WITH (FORMAT csv)") as cp:
            while chunk := f.read(1 << 20):
                cp.write(chunk)
        print(f"  loaded {anon}")
    values = (rl.ROOT / "setup" / "anonymize_values.sql").read_text(encoding="utf-8")
    conn.execute(values.replace("VACUUM ANALYZE;", ""))     # VACUUM cannot run inside the script's transaction
    conn.execute("VACUUM ANALYZE")
    print(f"Database {DB} ready.")


# --- queries ---------------------------------------------------------------

def rename_map():
    """{TPC-H name: anonymized name} for tables and columns, read from schema_anon.sql."""
    ddl = (rl.ROOT / "queries" / "schema_anon.sql").read_text(encoding="utf-8")
    blocks = dict(re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", ddl, re.DOTALL))
    mapping = {}
    for table, (anon, cols) in TPCH.items():
        anon_cols = re.findall(r"^\s+(col_\w+)\s", blocks[anon], re.MULTILINE)
        assert len(anon_cols) == len(cols), f"{anon}: {len(anon_cols)} columns, expected {len(cols)}"
        mapping[table] = anon
        mapping.update(zip(cols, anon_cols))
    return mapping


def anonymize(sql, mapping):
    """Rename tables and columns outside string literals; drop comments."""
    sql = re.sub(r"--[^\n]*", "", sql)
    pattern = re.compile(r"\b(" + "|".join(sorted(map(re.escape, mapping), key=len, reverse=True)) + r")\b")
    parts = re.split(r"('(?:[^']|'')*')", sql)       # odd positions are string literals: keep as is
    out = [p if i % 2 else pattern.sub(lambda m: mapping[m.group(1)], p) for i, p in enumerate(parts)]
    return re.sub(r"\n{3,}", "\n\n", "".join(out)).strip() + "\n"


def cmd_queries(args):
    """Write the anonymized held-out queries to results/pilots/queries/."""
    mapping = rename_map()
    out = PILOTS / "queries"
    out.mkdir(parents=True, exist_ok=True)
    for q in QUERIES:
        sql = (rl.ROOT / "setup" / "tpch_queries" / f"{q[0]}{int(q[1:])}.sql").read_text()
        (out / f"{q}.sql").write_text(anonymize(sql, mapping), encoding="utf-8")
        print(f"--- {q}\n{(out / f'{q}.sql').read_text()}")


def load_pilot_queries():
    return {q: (PILOTS / "queries" / f"{q}.sql").read_text(encoding="utf-8") for q in QUERIES}


# --- generate --------------------------------------------------------------

def cmd_generate(args):
    """Generate every (query, model, T, seed); resumable, model by model in shuffled order."""
    queries = load_pilot_queries()
    system, template, schema, sha = g.load_prompt()
    done = rl.already_generated(GENERATIONS)
    rng = random.Random(rl.CONFIG["shuffle_seed"])
    plan = []
    for model in rl.CONFIG["models"]:
        jobs = [(model, q, t, s) for q in QUERIES for t in TEMPERATURES for s in rl.SEEDS
                if rl.generation_key(q, FORM, model, s, t) not in done]
        rng.shuffle(jobs)
        plan.append((model, jobs))
    total = sum(len(j) for _, j in plan)
    print(f"{len(done)} already generated, {total} to do (prompt_sha {sha})")
    if not total:
        return
    ids = g.check_environment(list(rl.CONFIG["models"]), args.allow_mismatch)
    g.keep_awake()
    rl.log_environment({"pilot": "temperature", "prompt_sha": sha, "temperatures": list(TEMPERATURES)},
                       directory=PILOTS)       # everything of the pilot stays in results/pilots/
    n = 0
    for model, jobs in plan:
        if not jobs:
            continue
        print(f"\n== {model}: warm-up ...", flush=True)
        g.warm_up(model)
        for _, q, t, seed in jobs:
            n += 1
            print(f"[{n}/{total}] {q} T={t} seed={seed} ...", end=" ", flush=True)
            row = rl.generate_one(model, FORM, q, seed, g.build_prompt(template, schema, queries[q]),
                                  ids.get(model), GENERATIONS, system=system, prompt_sha=sha, temperature=t)
            print(f"{row['done_reason']}, parse_ok={row['parse_ok']}, {row['gen_time_ms'] / 1000:.1f} s")
    print(f"\nDone. Next: python pilots/pilot_temperature.py check")


# --- check -----------------------------------------------------------------

def normalize_text(sql):
    """Whitespace- and case-insensitive form, to count distinct rewrites."""
    return re.sub(r"\s+", " ", clean_sql(sql)).lower()


def cmd_check(args):
    """Run every rewrite on tpch_pilot, compare with the original query, summarize per (model, T)."""
    from db import classify_error, connect as db_connect, run_query
    queries = load_pilot_queries()
    conn = db_connect(DB, args.timeout_s)
    ref = {}
    for q, sql in queries.items():
        rows = run_query(conn, clean_sql(sql))
        ref[q] = (rows, has_top_level_order_by(sql))
        print(f"reference {q}: {len(rows)} rows" + ("   <-- EMPTY: cannot check correctness" if not rows else ""))

    rows_out = []
    for r in map(json.loads, open(GENERATIONS)):
        sql = clean_sql(r["sql"])
        status = "correct"
        if count_statements(sql) != 1:
            status = "not_single_statement"
        else:
            try:
                cand = run_query(conn, sql)
            except Exception as e:
                status = classify_error(e)
            else:
                ok, why = compare_results(ref[r["query_id"]][0], cand, ref[r["query_id"]][1], 4)
                status = "correct" if ok else "wrong_result"
        rows_out.append({"query_id": r["query_id"], "model": r["model"], "temperature": r["temperature"],
                         "seed": r["seed"], "status": status, "text": normalize_text(r["sql"])})

    PILOTS.mkdir(parents=True, exist_ok=True)
    with open(PILOTS / "temperature_rows.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["query_id", "model", "temperature", "seed", "status"],
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(rows_out)

    groups = defaultdict(list)
    for r in rows_out:
        groups[(r["model"], float(r["temperature"]))].append(r)
    summary = []
    for (model, t), rs in sorted(groups.items()):
        per_q = defaultdict(set)
        for r in rs:
            per_q[r["query_id"]].add(r["text"])
        summary.append({"model": model, "temperature": t, "n": len(rs),
                        "correct": sum(r["status"] == "correct" for r in rs),
                        "correct_rate": round(sum(r["status"] == "correct" for r in rs) / len(rs), 3),
                        "distinct_per_query": round(sum(len(v) for v in per_q.values()) / len(per_q), 2)})
    with open(PILOTS / "temperature_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)

    print(f"\n{'model':36s} {'T':>4s} {'n':>3s} {'correct':>8s} {'rate':>6s} {'distinct/query (max 5)':>24s}")
    for s in summary:
        print(f"{s['model']:36s} {s['temperature']:4.1f} {s['n']:3d} {s['correct']:8d} "
              f"{s['correct_rate']:6.2f} {s['distinct_per_query']:24.2f}")

    # Decision rule: highest T where both models stay within --tolerance of their lowest-T correctness
    temps = sorted({s["temperature"] for s in summary})
    base = {s["model"]: s["correct_rate"] for s in summary if s["temperature"] == temps[0]}
    ok_temps = [t for t in temps
                if all(s["correct_rate"] >= base[s["model"]] - args.tolerance
                       for s in summary if s["temperature"] == t)]
    print(f"\nRule: highest T with correctness within {args.tolerance:.2f} of T={temps[0]} "
          f"for both models -> T = {max(ok_temps) if ok_temps else 'none'}")
    print("With only 3 queries x 5 seeds per cell this is a rough guide; read the table, not just the rule.")


def main():
    p = argparse.ArgumentParser(description="Temperature pilot (C16).")
    p.add_argument("command", choices=["data", "db", "queries", "generate", "check"])
    p.add_argument("--sf", type=float, default=0.1, help="TPC-H scale factor (data)")
    p.add_argument("--tolerance", type=float, default=0.10, help="allowed drop in correctness rate (check)")
    p.add_argument("--timeout-s", type=float, default=60)
    p.add_argument("--allow-mismatch", action="store_true")
    args = p.parse_args()
    {"data": cmd_data, "db": cmd_db, "queries": cmd_queries,
     "generate": cmd_generate, "check": cmd_check}[args.command](args)


if __name__ == "__main__":
    main()
