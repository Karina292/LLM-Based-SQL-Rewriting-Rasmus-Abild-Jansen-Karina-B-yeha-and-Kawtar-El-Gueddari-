"""
pilot_memorization.py - memorization pilot (C8): does the anonymization hide TPC-H?

Professor's comment C8: show that the anonymization works. Decision rule (team
schedule): the anonymized schema must not be recognized as TPC-H; if it is, the
paper reports it as a threat to validity (the campaign data are frozen).

The test, kept in results/pilots/:

  recognize  Ask each model which benchmark a schema comes from, once with
             the original TPC-H DDL and once with the anonymized DDL
             (2 models x 2 schemas x 5 seeds = 20 calls, about 2 minutes).

Steps (on Rasmus' PC; needs Ollama):
  python pilot_memorization.py prompts      print the two schemas shown to the models
  python pilot_memorization.py recognize    -> results/pilots/memorization_recognition.jsonl/.csv
"""

import argparse
import csv
import json
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

import generate as g
import run_logger as rl
import pilot_temperature as pt

PILOTS = pt.PILOTS
T = rl.TEMPERATURE                        # 0.7, the frozen campaign temperature
RECOGNITION = PILOTS / "memorization_recognition.jsonl"

RECOGNITION_PROMPT = """Here is a database schema:

```sql
{schema}
```

Which public database benchmark or well-known sample database does this schema come from?
Answer on the first line with only its name, or NONE if you do not recognize it.
Then explain your answer in one sentence."""

# Named benchmarks / sample databases, checked in this order; the first match is the label.
_LABELS = [
    ("tpch", r"tpc[\s_-]*h\b|tpch\b"),
    ("other_tpc", r"tpc[\s_-]*(ds|c|e|di|bb|x)\b"),
    ("ssb", r"star\s*schema\s*benchmark|\bssb\b"),
    ("other_named", r"northwind|sakila|chinook|adventure\s*works|pagila|employees|world\b|imdb|\bjob\b"),
]


# --- schemas ---------------------------------------------------------------

def schemas():
    """{"anon": schema as in the campaign prompt, "tpch": same DDL with the original TPC-H names}.

    The original DDL is the anonymized one with every table and column renamed back, so
    the two differ only in names (same types, keys and order): any difference in the
    answers comes from the names alone.
    """
    anon = g.prompt_schema((rl.ROOT / rl.CONFIG["schema"]).read_text(encoding="utf-8"))
    back = {a: t for t, a in pt.rename_map().items()}
    return {"anon": anon, "tpch": pt.anonymize(anon, back).strip()}


def classify(answer):
    """Label of the model's answer: tpch, other_tpc, ssb, other_named, none or other."""
    text = (answer or "").strip().lower()
    first = text.splitlines()[0] if text else ""
    for label, pattern in _LABELS:              # the first line is the model's actual answer
        if re.search(pattern, first):
            return label
    if not first or re.match(r"\W*none\b", first) or "not recognize" in text or "don't recognize" in text:
        return "none"
    for label, pattern in _LABELS:              # name mentioned only in the explanation
        if re.search(pattern, text):
            return label
    return "other"


def cmd_prompts(args):
    for name, s in schemas().items():
        print(f"===== {name} =====\n{s}\n")


# --- 1. recognize ----------------------------------------------------------

def cmd_recognize(args):
    """Ask every model, for both schemas and every seed, which benchmark the schema is from."""
    sch = schemas()
    done = set()
    if RECOGNITION.exists():
        done = {(r["model"], r["schema"], r["seed"]) for r in map(json.loads, open(RECOGNITION))}
    jobs = [(m, s, seed) for m in rl.CONFIG["models"] for s in sch for seed in rl.SEEDS
            if (m, s, seed) not in done]
    print(f"{len(done)} already asked, {len(jobs)} to do")
    if jobs:
        ids = g.check_environment(list(rl.CONFIG["models"]), args.allow_mismatch)
        g.keep_awake()
        rl.log_environment({"pilot": "memorization", "prompt": RECOGNITION_PROMPT}, directory=PILOTS)
        random.Random(rl.CONFIG["shuffle_seed"]).shuffle(jobs)
        jobs.sort(key=lambda j: list(rl.CONFIG["models"]).index(j[0]))     # model by model
        PILOTS.mkdir(parents=True, exist_ok=True)
        for i, (model, s, seed) in enumerate(jobs, 1):
            resp = rl.ollama_generate(model, RECOGNITION_PROMPT.format(schema=sch[s]),
                                      {**rl.BASE_OPTIONS, "seed": seed})
            answer = resp.get("response", "")
            row = {"model": model, "model_id": ids.get(model), "schema": s, "seed": seed,
                   "temperature": T, "label": classify(answer), "answer": answer,
                   "output_tokens": resp.get("eval_count"),
                   "timestamp": datetime.now(timezone.utc).isoformat()}
            with open(RECOGNITION, "a") as f:
                f.write(json.dumps(row) + "\n")
            print(f"[{i}/{len(jobs)}] {model} {s} seed={seed}: {row['label']:12s} "
                  f"{answer.strip().splitlines()[0][:70] if answer.strip() else ''}")
    summarize_recognition()


def summarize_recognition():
    rows = list(map(json.loads, open(RECOGNITION)))
    for r in rows:                              # re-label, so a change of classify() applies to old rows
        r["label"] = classify(r["answer"])
    counts = defaultdict(Counter)
    for r in rows:
        counts[(r["model"], r["schema"])][r["label"]] += 1
    labels = ["tpch", "other_tpc", "ssb", "other_named", "other", "none"]
    out = []
    for (model, s), c in sorted(counts.items()):
        out.append({"model": model, "schema": s, "n": sum(c.values()), **{l: c[l] for l in labels}})
    with open(PILOTS / "memorization_recognition.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"\n{'model':36s} {'schema':6s} " + " ".join(f"{l:>11s}" for l in labels))
    for o in out:
        print(f"{o['model']:36s} {o['schema']:6s} " + " ".join(f"{o[l]:11d}" for l in labels))
    anon_hits = sum(o["tpch"] for o in out if o["schema"] == "anon")
    anon_n = sum(o["n"] for o in out if o["schema"] == "anon")
    print(f"\nAnonymized schema recognized as TPC-H in {anon_hits}/{anon_n} answers.")
    print("Read the answers in memorization_recognition.jsonl too: the labels come from a regex.")


def main():
    p = argparse.ArgumentParser(description="Memorization pilot (C8).")
    p.add_argument("command", choices=["prompts", "recognize"])
    p.add_argument("--allow-mismatch", action="store_true")
    args = p.parse_args()
    {"prompts": cmd_prompts, "recognize": cmd_recognize}[args.command](args)


if __name__ == "__main__":
    main()
