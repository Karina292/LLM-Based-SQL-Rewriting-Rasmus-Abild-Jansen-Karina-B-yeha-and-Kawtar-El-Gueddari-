"""
Tests the checker before the real measurements.

Six hand-written versions of TPC-H Q4 with a known verdict: two equivalent
ones, a changed filter, a reversed order, broken SQL and two statements.
Run on the database with the original TPC-H names:
    python measure/cli.py selftest --db tpch_sf01
It must end with "SELF-TEST PASSED".
"""

import json
from pathlib import Path

from io_files import read_csv

# Date filter shared by the three forms
Q4_WHERE = ("o_orderdate >= date '1993-07-01' "
            "and o_orderdate < date '1993-07-01' + interval '3' month")

# Using TPC-H Q4: number of orders per priority having at least one late line item

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

# Fake rewrites of the nested form, with the verdict the pipeline must give
SELFTEST_REWRITES = [
    (SELFTEST_FORMS["join"], "correct"),
    (SELFTEST_FORMS["cte"], "correct"),
    (SELFTEST_FORMS["join"].replace("1993-07-01", "1993-10-01"),
     "wrong_result"),                                          # changed date filter
    ("selec o_orderpriority from orders", "syntax_error"),     # invalid SQL
    (SELFTEST_FORMS["join"].replace("order by o_orderpriority", "order by o_orderpriority desc"),
     "wrong_result"),                                          # right rows, wrong order
    ("select 1; select 2", "multi_statement"),                 # two statements
]


def cmd_selftest(args, cmd_baseline, cmd_rewrites):
    """Write the test files, run the real pipeline, print PASS/FAIL per case.

    cmd_baseline and cmd_rewrites are passed in by cli.py (instead of being
    imported here) to avoid a circular import between the two modules.
    """
    root = Path("selftest")
    qdir, out = root / "queries", root / "results"
    qdir.mkdir(parents=True, exist_ok=True)
    for f in ("measurements.csv", "baselines.csv"):   # start from a clean state
        (out / f).unlink(missing_ok=True)
    for form, sql in SELFTEST_FORMS.items():
        (qdir / f"q04_{form}.sql").write_text(sql.strip() + "\n")
    gen_path = root / "generations.jsonl"
    with open(gen_path, "w") as f:
        for seed, (sql, _) in enumerate(SELFTEST_REWRITES):
            f.write(json.dumps({"query_id": "q04", "form": "nested", "model": "selftest",
                                "seed": seed, "temperature": 0.0, "sql": sql}) + "\n")
    args.queries, args.out = str(qdir), str(out)
    args.reps = min(args.reps, 5)                       # fewer repetitions: it is only a test
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
    if timed and not all(r["speedup"] for r in timed):  # every timed rewrite needs a speedup
        all_ok = False
        print("  speedup missing for a timed rewrite: FAIL")
    print("\nSELF-TEST", "PASSED" if all_ok and len(rows) == len(SELFTEST_REWRITES) else "FAILED")