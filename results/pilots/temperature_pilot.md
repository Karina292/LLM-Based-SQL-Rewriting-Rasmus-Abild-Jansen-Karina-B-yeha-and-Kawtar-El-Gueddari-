# Temperature pilot (C16)

*Rasmus, 26 October 2026. All files of the pilot are in `results/pilots/`; the campaign's `results/generations.jsonl` is not touched.*

**Question:** is T = 0.7 a good temperature? A1 said deterministic, A2 says T = 0.7, and the professor suggested a low value.

**Decision rule (team schedule):** the highest T whose correctness stays close to the lowest T, so that repeated runs still differ. "Close" was set to 0.10 (proposal in the schedule; adjustable).

**Result:** T = 0.7. The data support it as *not worse than lower values and more varied*, but they cannot separate T = 0.2 from T = 0.7 statistically (see limitations).

## Setup

| | |
|---|---|
| Queries | q14, q16, q22 (held out: among the 7 queries excluded from the main study, so tuning T cannot bias the main results) |
| Query form | original TPC-H form only (`orig`), anonymized with the same renaming as `schema_anon.sql` (`queries/`) |
| Models | `qwen2.5-coder:7b-instruct-q4_K_M` (`dae161e27b0e`), `llama3.1:8b-instruct-q4_K_M` (`46e0c10c039e`) |
| Temperatures | 0.2, 0.4, 0.7, 1.0 |
| Seeds | 1–5 → 3 queries × 2 models × 4 T × 5 seeds = **120 rewrites** (15 per model and T) |
| Prompt | same as the campaign (`setup/prompt_*.txt`, `prompt_sha` `11e2a496ae64`), same options (`num_ctx` 8192, model reloaded for every call) |
| Ollama | 0.40.11 on Windows 11, RTX 4060 Laptop GPU, on mains power |
| Correctness | rows of the rewrite = rows of the original query (`measure/compare.py`: multiset, rounding to 4 decimals, order if the original has `ORDER BY`) |
| Database | local PostgreSQL 18.6 (Windows), database `tpch_pilot`: `schema_anon.sql` + `setup/anonymize_values.sql`, TPC-H SF 0.1 |

The data were generated with **DuckDB's `dbgen`** (same row counts as TPC-H at SF 0.1, e.g. 600,572 lineitems), not the TPC-H reference `dbgen`. This is enough for a correctness check; no times were measured. Reference results: q14 1 row, q16 2,827 rows, q22 7 rows (none empty).

## Results

Per model and T (n = 15 each):

| Model | T | Correct | Rate | Distinct rewrites per query (max 5) |
|---|---|---|---|---|
| Llama 3.1 8B | 0.2 | 14 | 0.93 | 2.67 |
| | 0.4 | 10 | 0.67 | 5.00 |
| | 0.7 | 13 | 0.87 | 5.00 |
| | 1.0 | 9 | 0.60 | 4.67 |
| Qwen2.5-Coder 7B | 0.2 | 13 | 0.87 | 2.67 |
| | 0.4 | 14 | 0.93 | 3.33 |
| | 0.7 | 13 | 0.87 | 3.67 |
| | 1.0 | 12 | 0.80 | 4.33 |

Both models pooled (n = 30 per T), with 95 % Wilson intervals:

| T | Correct | Rate | 95 % interval |
|---|---|---|---|
| 0.2 | 27/30 | 0.90 | 0.74–0.97 |
| 0.4 | 24/30 | 0.80 | 0.63–0.90 |
| 0.7 | 26/30 | 0.87 | 0.70–0.95 |
| 1.0 | 21/30 | 0.70 | 0.52–0.83 |

Failures of the 22 incorrect rewrites: 15 SQL errors, 6 wrong results, 1 syntax error. All 120 outputs parsed and finished normally (`done_reason` = `stop`). None of the 98 correct rewrites is an unchanged copy of the input.

## Observations

- **Correctness falls only at T = 1.0.** Between 0.2 and 0.7 the differences are within noise (the intervals overlap almost completely; Llama at T = 0.4 is lower than at 0.7, which shows how little 15 rewrites per cell can decide).
- **Low T wastes seeds.** At T = 0.2 only about 2.7 of the 5 rewrites per query are different, so N = 5 explores fewer rewrites. At T = 0.7 it is 3.7 (Qwen) to 5.0 (Llama). This matters because the paper studies how stable the rewrites are.
- **Rule outcome:** highest T within 0.10 of the T = 0.2 correctness for both models → **T = 0.7**.

## For the paper (Experimental Setup, C16)

- A1 "deterministic" → A2 "T = 0.7": identical runs cannot measure how stable a model's rewrites are, which is part of the research question.
- The pilot supports T = 0.7: correctness comparable to T = 0.2, clearly more varied rewrites, and lower correctness at T = 1.0.
- State the limits openly (below).

## Limitations

- Only 3 queries, 2 models and 5 seeds per cell; the pilot cannot distinguish T = 0.2 from T = 0.7 (intervals about ±0.12–0.18).
- Original form only; the main study has three forms.
- q14, q16 and q22 have a different structure than the 15 main queries (they were excluded because they could not be written naturally in all three forms).
- Correctness only; speedup was not part of the pilot.
- Data generated with DuckDB's `dbgen` and a local PostgreSQL 18.6, not the group's measurement databases.

## Files

| File | Content |
|---|---|
| `temperature_generations.jsonl` | the 120 rewrites (same format as `results/generations.jsonl`, with `temperature` per row) |
| `temperature_rows.csv` | status of each rewrite (`correct`, `sql_error`, `wrong_result`, …) |
| `temperature_summary.csv` | table per model and T |
| `queries/q14.sql`, `q16.sql`, `q22.sql` | the anonymized held-out queries |
| `env_gen_*.json` | environment of the run |

## Reproduce

```bash
python pilot_temperature.py data
python pilot_temperature.py db          # needs PGUSER=postgres PGHOST=127.0.0.1 (no password on this PC)
python pilot_temperature.py queries
python pilot_temperature.py generate    # on Windows (Ollama), on mains power
python pilot_temperature.py check
```

Generation is reproducible because the model is reloaded for every call (see `generation_changes.md`).
