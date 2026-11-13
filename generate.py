"""
generate.py - generation phase: send every input query to the LLMs (run on Rasmus' PC).

Commands:
  python generate.py --dry-run --queries q03
      Print the exact prompt for one job, call nothing.
  python generate.py --queries q03 q05
      Generate all forms x models x seeds of these queries (resumable).
  python generate.py
      Generate everything in queries/ that is not in generations.jsonl yet.
  python generate.py --verify 20
      Re-generate 20 random logged rewrites and check that each seed gives
      exactly the same SQL again (reproducibility evidence, nothing is logged
      to generations.jsonl; the result goes to results/verify_<time>.json).

Options: --models (all in the config), --limit N (stop after N generations),
         --out (results/generations.jsonl), --allow-mismatch

Settings come from setup/generation_config.json, the prompt from
setup/prompt_system.txt (fixed instruction, A2 section 3.3) and
setup/prompt_user.txt (schema + query). Each rewrite is logged by
run_logger.py; push results/generations.jsonl after each query so Kawtar
can measure it.

Before a run:
  - the Ollama version and model IDs are checked against the config, so the
    weights cannot change during the campaign without us noticing;
  - the PC must run on mains power (on battery, Windows lowers the clocks);
  - each model gets one untimed warm-up call, so its file is read from disk
    once before logging starts (later reloads come from the OS file cache).
While running, Windows is asked not to go to sleep (released when the script ends).
Every call reloads the model (keep_alive = 0, see run_logger.ollama_generate),
so no call reuses the cached prompt of the previous one and each seed is
reproducible. Jobs are run model by model, in shuffled order within each
model, so thermal drift is spread over queries, forms and seeds. The shuffle uses a fixed seed: the order is repeatable.
"""

import argparse
import ctypes
import hashlib
import json
import random
import re
import sys
from datetime import datetime
from pathlib import Path

import run_logger as rl

sys.path.insert(0, str(rl.ROOT / "measure"))
from io_files import load_input_queries   # same file naming rules as measure/

CONFIG = rl.CONFIG

# Strings are matched (and kept) so that "--" or "/*" inside a literal is not taken as a comment.
_STRING_OR_COMMENT = re.compile(r"('(?:[^']|'')*'|\"[^\"]*\")|--[^\n]*|/\*.*?\*/", re.DOTALL)
_MARK = "\0"


def strip_comments(sql):
    """Remove SQL comments, keep string literals; drop lines that only held a comment.

    Needed because the query files start with "/* using ... seed to the RNG */"
    (TPC-H qgen output) and the schema with "-- Anonymized TPC-H Schema ...":
    both would tell the model it is looking at TPC-H.
    """
    marked = _STRING_OR_COMMENT.sub(lambda m: m.group(1) or _MARK, sql)
    lines = [ln for ln in marked.splitlines() if ln.replace(_MARK, "").strip() or _MARK not in ln]
    return "\n".join(ln.replace(_MARK, "").rstrip() for ln in lines).strip()


def prompt_schema(ddl):
    """Schema as shown to the model: no comments, no DROP TABLE statements."""
    s = strip_comments(ddl)
    s = re.sub(r"^DROP TABLE[^;]*;[ \t]*$\n?", "", s, flags=re.MULTILINE | re.IGNORECASE)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def load_prompt():
    """Return (system text, user template, schema text, prompt_sha).

    prompt_sha identifies this exact prompt version (instruction + template + schema);
    it is stored with every rewrite, so a change in the prompt is visible in the data.
    """
    system = (rl.ROOT / CONFIG["prompt_system"]).read_text(encoding="utf-8").strip()
    template = (rl.ROOT / CONFIG["prompt_user"]).read_text(encoding="utf-8")
    schema = prompt_schema((rl.ROOT / CONFIG["schema"]).read_text(encoding="utf-8"))
    sha = hashlib.sha256("\n\0".join([system, template, schema]).encode()).hexdigest()[:12]
    return system, template, schema, sha


def build_prompt(template, schema, query_sql):
    """User message for one input query (comments removed)."""
    return template.replace("{schema}", schema).replace("{query}", strip_comments(query_sql))


def on_mains_power():
    """True on mains power, False on battery, None if unknown (not Windows)."""
    class _Status(ctypes.Structure):
        _fields_ = [("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                    ("BatteryLifePercent", ctypes.c_byte), ("SystemStatusFlag", ctypes.c_byte),
                    ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
    try:
        s = _Status()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
            return None
        return {0: False, 1: True}.get(s.ACLineStatus)
    except (AttributeError, OSError):
        return None


def keep_awake():
    """Ask Windows not to sleep while this process runs (no setting is changed;
    the request ends with the process). Does not stop sleep when the lid is closed."""
    try:
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    except (AttributeError, OSError):
        pass


def check_environment(models, allow_mismatch):
    """Stop if on battery, or if the Ollama version or a model ID differs from the config."""
    problems = []
    if on_mains_power() is False:
        problems.append("running on battery: plug in the charger")
    version = rl._cmd(["ollama", "--version"]) or ""
    if CONFIG["ollama_version"] not in version:
        problems.append(f"Ollama version: expected {CONFIG['ollama_version']}, got '{version}'")
    ids = rl.model_ids()
    for m in models:
        if ids.get(m) != CONFIG["models"][m]:
            problems.append(f"{m}: expected ID {CONFIG['models'][m]}, got {ids.get(m)}")
    for p in problems:
        print("  !", p)
    if problems and not allow_mismatch:
        sys.exit("Environment differs from setup/generation_config.json (use --allow-mismatch to run anyway).")
    return ids


def warm_up(model):
    """One untimed call so the model is loaded on the GPU before logging starts."""
    rl.ollama_generate(model, "SELECT 1;", {**rl.BASE_OPTIONS, "seed": 0})


def verify(n, out, queries, system, template, schema, sha):
    """Re-generate n random logged rewrites and compare the SQL with the logged one.

    Uses only rows made with the current prompt (same prompt_sha). The sample is
    drawn with a fixed seed, so the same rows are re-checked if run again.
    """
    rows = [r for r in map(json.loads, open(out)) if r.get("prompt_sha") == sha]
    if not rows:
        sys.exit("No rewrites with the current prompt to verify.")
    sample = random.Random(CONFIG["shuffle_seed"]).sample(rows, min(n, len(rows)))
    sample.sort(key=lambda r: r["model"])          # model by model, like the campaign
    check_environment(sorted({r["model"] for r in sample}), False)
    keep_awake()
    results, model = [], None
    for i, r in enumerate(sample, 1):
        if r["model"] != model:
            model = r["model"]
            warm_up(model)
        resp = rl.ollama_generate(model, build_prompt(template, schema, queries[(r["query_id"], r["form"])]),
                                  {**rl.BASE_OPTIONS, "seed": r["seed"]}, system)
        same = rl.extract_sql(resp.get("response", "")) == r["sql"]
        results.append({k: r[k] for k in ("query_id", "form", "model", "seed")} | {"identical": same})
        print(f"[{i}/{len(sample)}] {r['query_id']} {r['form']} {model} seed={r['seed']}: "
              f"{'identical' if same else 'DIFFERENT'}")
    n_same = sum(x["identical"] for x in results)
    path = rl.RESULTS / f"verify_{datetime.now().strftime('%Y-%m-%dT%H%M%S')}.json"
    with open(path, "w") as f:
        json.dump({"prompt_sha": sha, "checked": len(results), "identical": n_same,
                   "rows": results}, f, indent=1)
    print(f"\n{n_same}/{len(results)} identical. Saved {path}")


def main():
    p = argparse.ArgumentParser(description="Generate LLM rewrites of the input queries.")
    p.add_argument("--queries", nargs="*", help="query ids, e.g. q03 q05 (default: all)")
    p.add_argument("--models", nargs="*", default=list(CONFIG["models"]))
    p.add_argument("--limit", type=int, help="stop after N generations")
    p.add_argument("--out", default=str(rl.GENERATIONS_FILE))
    p.add_argument("--dry-run", action="store_true", help="print one prompt, call nothing")
    p.add_argument("--verify", type=int, metavar="N",
                   help="re-generate N logged rewrites and check they are identical")
    p.add_argument("--allow-mismatch", action="store_true")
    args = p.parse_args()

    unknown = [m for m in args.models if m not in CONFIG["models"]]
    if unknown:
        sys.exit(f"Not in the config: {unknown}")
    queries = load_input_queries(rl.ROOT / CONFIG["queries_dir"])
    qids = sorted({q for q, _ in queries})
    if args.queries:
        missing = [q for q in args.queries if q not in qids]
        if missing:
            sys.exit(f"No input files for {missing}")
        qids = args.queries
    system, template, schema, sha = load_prompt()

    if args.dry_run:
        q, f = qids[0], CONFIG["forms"][0]
        print(f"--- system ---\n{system}\n--- user ({q} {f}, prompt_sha {sha}) ---")
        print(build_prompt(template, schema, queries[(q, f)]))
        return
    if args.verify:
        verify(args.verify, args.out, queries, system, template, schema, sha)
        return

    done = rl.already_generated(args.out)
    rng = random.Random(CONFIG["shuffle_seed"])
    plan = []
    for model in args.models:
        jobs = [(model, f, q, s) for q in qids for f in CONFIG["forms"] for s in rl.SEEDS
                if (q, f) in queries and rl.generation_key(q, f, model, s) not in done]
        rng.shuffle(jobs)
        plan.append((model, jobs))
    total = sum(len(j) for _, j in plan)
    print(f"{len(done)} already generated, {total} to do (prompt_sha {sha})")
    if total == 0:
        return

    ids = check_environment(args.models, args.allow_mismatch)
    keep_awake()
    rl.log_environment({"prompt_sha": sha, "config": CONFIG, "queries": qids,
                        "on_mains_power": on_mains_power(),
                        "power_scheme": rl._cmd(["powercfg", "/getactivescheme"])})
    n = 0
    for model, jobs in plan:
        if not jobs:
            continue
        print(f"\n== {model}: warm-up ...", flush=True)
        warm_up(model)
        for _, form, qid, seed in jobs:
            if args.limit is not None and n >= args.limit:
                print(f"\nStopped after --limit {args.limit}.")
                return
            n += 1
            print(f"[{n}/{total}] {qid} {form} seed={seed} ...", end=" ", flush=True)
            row = rl.generate_one(model, form, qid, seed,
                                  build_prompt(template, schema, queries[(qid, form)]),
                                  ids.get(model), args.out, system=system, prompt_sha=sha)
            print(f"{row['done_reason']}, parse_ok={row['parse_ok']}, "
                  f"{row['gen_time_ms'] / 1000:.1f} s, {row['output_tokens']} tokens")
    print(f"\nDone. Push {args.out} so the rewrites can be measured.")


if __name__ == "__main__":
    main()
