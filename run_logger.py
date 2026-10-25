"""Generation and logging of LLM rewrites -> results/generations.jsonl.

One line per rewrite, in the format read by measure/ (see measure/io_files.py):
    query_id, form, model, seed, temperature, sql          (required by measure)
    model_id, num_ctx, parse_ok, done_reason, raw_response,
    gen_time_ms, prompt_eval_ms, eval_ms, load_ms, total_ms,
    prompt_tokens, prompt_cached_tokens, output_tokens, gpu_before, gpu_after, timestamp

- log_environment():  call once per session -> results/env_gen_<time>.json
- generate_one(...):  call once per rewrite -> one line in generations.jsonl
- already_generated(): keys already in the file, to resume after a crash

Settings follow A2: T = 0.7, one fixed seed per generation (1 to 5),
num_ctx = 8192, every other Ollama option left at its default.
"""

import json
import os
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

try:
    import sqlglot
except ImportError:
    sqlglot = None      # parse_ok is then recorded as None

RESULTS = Path(__file__).resolve().parent / "results"
GENERATIONS_FILE = RESULTS / "generations.jsonl"

TEMPERATURE = 0.7
SEEDS = (1, 2, 3, 4, 5)                 # N = 5, one fixed seed per generation
BASE_OPTIONS = {"temperature": TEMPERATURE, "num_ctx": 8192}


def _cmd(args):
    """Run a shell command and return its output, or None if it fails."""
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return None


def _int_or_none(s):
    """int(s), or None for values like "[N/A]" that nvidia-smi sometimes reports."""
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def gpu_snapshot():
    """Read GPU state via nvidia-smi. Never raises: a failed reading gives None
    (or None fields), so it cannot stop an overnight run."""
    out = _cmd([
        "nvidia-smi",
        "--query-gpu=temperature.gpu,utilization.gpu,clocks.sm,memory.used",
        "--format=csv,noheader,nounits",
    ])
    if not out:
        return None
    vals = [x.strip() for x in out.splitlines()[0].split(",")]
    if len(vals) != 4:
        return None
    temp, util, clock, mem = (_int_or_none(v) for v in vals)
    return {"temp_c": temp, "util_pct": util, "sm_clock_mhz": clock, "mem_used_mib": mem}


def model_ids():
    """{model tag: Ollama ID} from `ollama list`, e.g. {"llama3.1:8b-instruct-q4_K_M": "46e0c10c039e"}.

    The ID changes if the weights change, so it proves the same model was used throughout.
    """
    out = _cmd(["ollama", "list"]) or ""
    ids = {}
    for line in out.splitlines()[1:]:       # first line is the header
        parts = line.split()
        if len(parts) >= 2:
            ids[parts[0]] = parts[1]
    return ids


def log_environment():
    """Save the setup of this session, so the run can be described in the method section.

    One file per session (timestamped), so earlier sessions are not overwritten.
    Note: ollama_env shows the OLLAMA_* variables of this Python process; if the
    Ollama server was started elsewhere (service, other shell) its settings may differ.
    """
    now = datetime.now(timezone.utc)
    env = {
        "timestamp": now.isoformat(),
        "kernel": platform.release(),
        "cpu_count": os.cpu_count(),
        "ollama_version": _cmd(["ollama", "--version"]),
        "model_ids": model_ids(),
        "gpu": _cmd(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"]),
        "ollama_env": {k: v for k, v in os.environ.items() if k.startswith("OLLAMA_")},
        "options": {**BASE_OPTIONS, "seeds": list(SEEDS)},
        "sqlglot_version": getattr(sqlglot, "__version__", None),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"env_gen_{now.strftime('%Y-%m-%dT%H%M%S')}.json"
    with open(path, "w") as f:
        json.dump(env, f, indent=2)
    return path


# ```sql ... ``` (or ``` ... ```, ```postgresql ...); DOTALL so the block can span lines
_FENCE = re.compile(r"```[ \t]*([A-Za-z]*)[ \t]*\n(.*?)```", re.DOTALL)


def extract_sql(text):
    """Get the SQL out of the model's answer.

    Models usually wrap the query in a markdown block and may add explanations.
    Takes the first block labelled sql/postgres(ql), else the first block of any
    kind, else the whole answer. If the answer was cut off, the block may have no
    closing ```; the text after the opening fence is then used.
    Not extracting would make measure/ report a syntax_error that is really ours.
    """
    text = text or ""
    blocks = _FENCE.findall(text)
    for lang, body in blocks:
        if lang.lower() in ("sql", "postgres", "postgresql", "psql"):
            return body.strip()
    if blocks:
        return blocks[0][1].strip()
    open_fence = re.search(r"```[ \t]*[A-Za-z]*[ \t]*\n", text)
    if open_fence:                                  # unclosed block (truncated answer)
        return text[open_fence.end():].strip()
    return text.strip()


def parse_ok(sql):
    """True if SQLGlot parses `sql` as PostgreSQL, False if not, None if SQLGlot is missing.

    Only a quick check for the generation log; measure/ decides correctness on the database.
    SQLGlot is lenient ("SELEC x" parses as a column alias), so every parsed
    statement must also be a query (SELECT, WITH ... SELECT, UNION, ...).
    """
    if sqlglot is None:
        return None
    if not sql.strip():
        return False
    try:
        stmts = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except Exception:
        return False
    return bool(stmts) and all(isinstance(s, sqlglot.exp.Query) for s in stmts)


def _get(resp, key, default=None):
    """Field of an Ollama response: a dict in old ollama-python, an object since 0.4."""
    if isinstance(resp, dict):
        return resp.get(key, default)
    val = getattr(resp, key, default)
    return default if val is None else val


def generation_key(query_id, form, model, seed, temperature=TEMPERATURE):
    """Same key as rewrite_key in measure/io_files.py (all as strings)."""
    return (str(query_id), str(form), str(model), str(seed), str(temperature))


def already_generated(path=GENERATIONS_FILE):
    """Keys of the rewrites already in generations.jsonl (to skip them on resume)."""
    done = set()
    if not Path(path).exists():
        return done
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
                done.add(generation_key(r["query_id"], r["form"], r["model"],
                                        r["seed"], r.get("temperature", "")))
            except (json.JSONDecodeError, KeyError):
                pass        # corrupted line (interrupted write): measure/ skips it too
    return done


def log_generation(query_id, form, model, seed, response, gpu_before, gpu_after,
                   model_id=None, path=GENERATIONS_FILE):
    """Append one rewrite to generations.jsonl and return the row.

    `response` is what ollama.generate() returned. Ollama durations are in
    nanoseconds. gen_time_ms = prompt evaluation + output generation; model
    load time is kept separately (load_ms) and not counted, since it depends
    on what was loaded before, not on the query.
    """
    raw = _get(response, "response", "") or ""
    sql = extract_sql(raw)
    prompt_eval_ms = _get(response, "prompt_eval_duration", 0) / 1e6
    eval_ms = _get(response, "eval_duration", 0) / 1e6
    row = {
        "query_id": query_id,
        "form": form,
        "model": model,
        "model_id": model_id,
        "seed": seed,
        "temperature": TEMPERATURE,
        "num_ctx": BASE_OPTIONS["num_ctx"],
        "sql": sql,
        "parse_ok": parse_ok(sql),
        # "stop" = finished normally, "length" = cut off (num_predict / num_ctx reached)
        "done_reason": _get(response, "done_reason"),
        "gen_time_ms": round(prompt_eval_ms + eval_ms, 3),
        "prompt_eval_ms": round(prompt_eval_ms, 3),
        "eval_ms": round(eval_ms, 3),
        "load_ms": round(_get(response, "load_duration", 0) / 1e6, 3),
        "total_ms": round(_get(response, "total_duration", 0) / 1e6, 3),
        "prompt_tokens": _get(response, "prompt_eval_count"),
        # prompt tokens reused from Ollama's cache (newer Ollama only, else None): when the
        # same prompt ran just before, prompt_eval_ms drops to almost nothing
        "prompt_cached_tokens": _get(response, "prompt_eval_cached_count"),
        "output_tokens": _get(response, "eval_count"),
        "gpu_before": gpu_before,
        "gpu_after": gpu_after,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "raw_response": raw,    # full answer, to check the extraction afterwards
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(row) + "\n")
        f.flush()
        os.fsync(f.fileno())    # crash-safe, like append_csv in measure/
    return row


def generate_one(model, form, query_id, seed, prompt, model_id=None, path=GENERATIONS_FILE):
    """Call the model once with the A2 settings and log the result.

    The seed goes into the options of this call, so each of the N generations
    is reproducible on its own.
    """
    import ollama   # imported here so the logging helpers work without ollama installed
    before = gpu_snapshot()
    resp = ollama.generate(model=model, prompt=prompt, options={**BASE_OPTIONS, "seed": seed})
    after = gpu_snapshot()
    return log_generation(query_id, form, model, seed, resp, before, after, model_id, path)


# --- Example use ---------------------------------------------------------
# import random
# from run_logger import (SEEDS, already_generated, generate_one, generation_key,
#                         log_environment, model_ids)
#
# log_environment()
# ids = model_ids()
# done = already_generated()
#
# jobs = [(m, f, q, s) for m in MODELS for f in FORMS for q in QUERIES for s in SEEDS
#         if generation_key(q, f, m, s) not in done]           # resume: skip what exists
# random.shuffle(jobs)  # mixed order spreads thermal drift across all conditions
#
# for model, form, query_id, seed in jobs:
#     row = generate_one(model, form, query_id, seed, build_prompt(form, query_id), ids.get(model))
#     print(query_id, form, model, seed, row["done_reason"], row["parse_ok"])
