"""
db.py - everything that talks to PostgreSQL: connection, execution, timing.

Timing protocol (time_query):
  1. W warm-up executions, not recorded (default W = 1, --warmup)
  2. R executions with EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
     (default R = 20, --reps); we record PostgreSQL's "Execution Time"
  3. the median of the R times is used (stats)

Methodological notes:
  - Warm-up loads the table pages into memory, so that the first (cold)
    run does not penalize whichever query happens to run first.
  - Median rather than mean: one run slowed down by the OS does not shift it.
  - EXPLAIN ANALYZE adds some instrumentation overhead, but in the same way
    for the input query and the rewrite, so the speedup ratio stays valid.
  - "Execution Time" excludes the time to send rows to the client and the
    planning time; we measure the query execution itself.
"""

import json
import statistics
import sys

try:
    import psycopg
    from psycopg import errors as pgerr
except ImportError:
    # The modules sql_text, compare, plans can still be imported and
    # tested without psycopg; connect() gives a clear message instead.
    psycopg = None
    pgerr = None


def connect(db, timeout_s):
    """Open a connection to database `db` on the local server.

    - autocommit=True: each query runs on its own. Without it, a failing
      rewrite would leave the transaction aborted and block the next ones.
    - statement_timeout: any query running longer than `timeout_s` seconds
      (default 60, --timeout-s) is cancelled and recorded as "timeout",
      so one catastrophic rewrite cannot block the whole campaign.
    """
    if psycopg is None:
        sys.exit("psycopg is not installed: pip install 'psycopg[binary]'")
    conn = psycopg.connect(dbname=db, autocommit=True)
    conn.execute(f"SET statement_timeout = {int(timeout_s * 1000)}")  # in ms
    return conn


def run_query(conn, sql):
    """Execute `sql` and return all rows as a list of tuples.

    Used for the correctness check (the rows are passed to compare.py).
    Returns [] for statements that produce no rows.
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall() if cur.description else []


def explain_analyze(conn, sql):
    """Execute `sql` for real and return its measured plan.

    EXPLAIN ANALYZE runs the query (it does not just estimate) and returns
    the plan annotated with real timings. The result is a dict with, among
    others:
        "Plan"            the plan tree (used by plans.py)
        "Execution Time"  real execution time in milliseconds
    BUFFERS adds memory/disk page counts, kept in the saved plan files.
    """
    with conn.cursor() as cur:
        cur.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql)
        doc = cur.fetchone()[0]
    if isinstance(doc, str):        # depending on the driver, JSON may come as text
        doc = json.loads(doc)
    return doc[0]


def classify_error(exc):
    """Map a database error to a failure category for measurements.csv.

        timeout       query cancelled by statement_timeout
        syntax_error  invalid SQL (e.g. a typo produced by the LLM)
        sql_error     valid SQL that fails anyway, e.g. a table or column
                      the LLM invented, or a type mismatch
    """
    if pgerr is not None and isinstance(exc, pgerr.QueryCanceled):
        return "timeout"
    if pgerr is not None and isinstance(exc, pgerr.SyntaxError):
        return "syntax_error"
    return "sql_error"


def time_query(conn, sql, warmup, reps):
    """Apply the timing protocol (see top of file) to one query.

    Returns (times_ms, last_plan_doc):
        times_ms      list of the R execution times in milliseconds
        last_plan_doc plan of the last run, saved and summarized afterwards
    """
    for _ in range(warmup):         # not recorded
        run_query(conn, sql)
    times, doc = [], None
    for _ in range(reps):
        doc = explain_analyze(conn, sql)
        times.append(float(doc["Execution Time"]))
    return times, doc


def stats(times):
    """Summary statistics of a list of times (ms), as stored in the CSVs.

    median_ms is the value used for the speedup. All raw times are kept in
    times_ms ("12.3;11.9;...") so dispersion, confidence intervals or the
    choice of R can be re-analyzed later without re-measuring.
    """
    return {
        "median_ms": round(statistics.median(times), 3),
        "mean_ms": round(statistics.fmean(times), 3),
        "std_ms": round(statistics.stdev(times), 3) if len(times) > 1 else 0.0,
        "min_ms": round(min(times), 3),
        "max_ms": round(max(times), 3),
        "times_ms": ";".join(f"{t:.3f}" for t in times),
    }