"""
Reading the inputs and writing the results.

Inputs:  query files named qXX_<form>.sql (the measured ones are in
         results/queries_used/) and results/generations.jsonl (one rewrite per line).
Outputs: results/baselines.csv, results/measurements.csv (one row per rewrite)
         and the full plans in results/plans/.

The column lists below are used by the analysis scripts, so don't change
them without telling the group.
"""

import csv
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

FORMS = ("nested", "join", "cte")   # the three structural variants, in this order

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


def now():
    """Current date and time, stored with each measurement (e.g. 2026-10-20T00:30:12)."""
    return dt.datetime.now().isoformat(timespec="seconds")


def read_csv(path):
    """Read a CSV as a list of dicts (column name -> value); [] if it does not exist yet."""
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def append_csv(path, fields, row):
    """Append one row to a CSV, writing the header if the file is new.

    The row is written to disk immediately (flush + fsync): if the machine
    crashes during an overnight run, every measurement already made is kept,
    and the next run resumes from there (see rewrite_key).
    """
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
    """Load the input queries from `qdir`.

    File names must be <query_id>_<form>.sql, e.g. q04_nested.sql.
    Returns {(query_id, form): sql_text}, e.g. {("q04", "nested"): "select ..."}.
    Files with another name pattern are ignored.
    """
    out = {}
    for p in sorted(Path(qdir).glob("*.sql")):
        m = re.match(r"(.+)_(nested|join|cte)$", p.stem)   # p.stem = name without .sql
        if m:
            out[(m.group(1), m.group(2))] = p.read_text()
    if not out:
        sys.exit(f"No files like q04_nested.sql found in {qdir}")
    return out


def load_generations(path):
    """Load the LLM rewrites: one JSON object per line (JSONL).

    A corrupted line (e.g. a run interrupted while writing) is reported and
    skipped instead of stopping the whole campaign.
    """
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
    """Unique identifier of one rewrite: (query_id, form, model, seed, temperature).

    Used to resume: rewrites whose key is already in measurements.csv are
    skipped, so the script can be re-run after each new batch from Rasmus.
    """
    return (str(r["query_id"]), str(r["form"]), str(r["model"]),
            str(r["seed"]), str(r.get("temperature", "")))


def save_plan(out, name, doc, signature):
    """Save the full EXPLAIN output and its signature in <out>/plans/<name>.json.

    Special characters in `name` are replaced by "_" to get a valid file name
    (model names like "qwen2.5-coder:7b" contain ":").
    """
    pdir = out / "plans"
    pdir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    with open(pdir / f"{safe}.json", "w") as f:
        json.dump({"signature": signature, "explain": doc}, f, indent=1, default=str)