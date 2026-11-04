# Memorization pilot (C8)

*Rasmus, 4 November 2026. All files of the pilot are in `results/pilots/`.*

**Question (C8):** does the anonymization hide that the schema is TPC-H? The paper claims we anonymize "to prevent benchmark memorization" (Section 3.3); the professor asked us to show that it works.

**Decision rule (team schedule):** the anonymized schema must not be recognized as TPC-H. If it is, the anonymization should be strengthened; since the campaign data are frozen, that would now go into the threats to validity instead.

**Result:** the anonymization works for the most part. With the original names, the models name TPC-H in 7 of 10 answers. With the anonymized schema it is 1 of 10 (p = 0.02).

## Setup

| | |
|---|---|
| Models | `qwen2.5-coder:7b-instruct-q4_K_M` (`dae161e27b0e`), `llama3.1:8b-instruct-q4_K_M` (`46e0c10c039e`) |
| Options | T = 0.7, seeds 1–5, `num_ctx` 8192, model reloaded for every call (same as the campaign) |
| Ollama | **0.40.13** on Windows 11, RTX 4060 Laptop GPU, on mains power. Ollama had updated itself; the campaign and the temperature pilot used 0.40.11. Run with `--allow-mismatch`; model IDs unchanged |
| Original schema | `queries/schema_anon.sql` with every table and column renamed back to TPC-H (`region`, `r_regionkey`, …). Types, keys and column order are identical, so the two schemas differ only in names |
| Script | `pilot_memorization.py` (`prompts`, `recognize`) |

**Test.** Each model gets one schema and the question *"Which public database benchmark or well-known sample database does this schema come from? Answer on the first line with only its name, or NONE if you do not recognize it. Then explain your answer in one sentence."*. 2 models × 2 schemas × 5 seeds = 20 answers.

## Results

### Recognition (n = 5 per cell)

| Model | Schema | TPC-H | Other TPC benchmark | Other answer | NONE |
|---|---|---|---|---|---|
| Llama 3.1 8B | original | 3 | 2 (TPC-DS, TPC-D) | 0 | 0 |
| | anonymized | **1** | 0 | 1 (LINQ / Northwind) | 3 |
| Qwen2.5-Coder 7B | original | 4 | 0 | 1 (SAP BusinessObjects) | 0 |
| | anonymized | **0** | 0 | 1 (invented "DAMO") | 4 |

Both models pooled, with 95 % Wilson intervals:

| Schema | Named TPC-H | Rate | 95 % interval |
|---|---|---|---|
| original | 7/10 | 0.70 | 0.40–0.89 |
| anonymized | 1/10 | 0.10 | 0.02–0.40 |

Fisher's exact test, two-sided: p = 0.02. With the original names, 9 of 10 answers point to a TPC decision-support benchmark (TPC-H, or its predecessor TPC-D, or TPC-DS). With the anonymized schema, 7 of 10 answers are NONE, and the answers that name something name the wrong thing, except one.

The one hit (Llama, seed 4) answered *"LINEITEM … This schema comes from the TPC-H benchmark"*. `lineitem` does not occur in the anonymized schema (`tbl_items`), so this is genuine recognition, from the table structure. All labels were checked by hand against the full answers in `memorization_recognition.jsonl`. One Qwen answer labelled NONE mentions TPC-H only as an example of what the schema is *not*.

## Observations

- **Anonymization removes most of the recognition.** The share of answers naming TPC-H falls from 0.70 to 0.10 (p = 0.02). The schema still has the TPC-H structure (8 tables, the same keys and column order), and Llama recognized it once from that alone. The anonymization hides the names, not the structure.
- **Rule outcome:** the anonymized schema is not reliably recognized (1/10) → **no change to the anonymization needed**; report the one recognition and the kept structure as a limitation.

## For the paper (Section 4.5 Benchmark Recognition, with references from 3.3 and the Discussion; C8, C14)

- 4.5: *"To check that the anonymization hides the benchmark, we gave each model the schema DDL and asked which public benchmark or sample database it comes from, once with the original TPC-H names and once with the anonymized names (5 seeds per model and schema, T = 0.7). With the original names, 7 of 10 answers named TPC-H; with the anonymized schema, 1 of 10 did. This difference is significant at the 5% level (Fisher's exact test, p = 0.02 < 0.05), i.e. unlikely to be due to chance, and 7 of 10 answers with the anonymized schema stated that they did not recognize it. The single recognition (Llama 3.1, seed 4) named TPC-H and even its original table `lineitem`, although the prompt only contained the anonymized name `tbl_items`; it must have recognized the table structure, which the anonymization keeps."*
- Threats to validity: the anonymization changes names but keeps the structure of the schema and most TPC-H literals in the queries (e.g. `'Brand#44'`, `'PROMO%'`), so partial recognition cannot be excluded.

## Limitations

- Small samples: 10 answers per schema; only large effects are visible.
- The question names "benchmark", which invites a benchmark answer; this works against the anonymization, so the 1/10 is conservative.
- The recognition test shows the schema only. The queries also keep TPC-H literals and were not tested on their own.
- Run on Ollama 0.40.13 instead of the campaign's 0.40.11 (model IDs unchanged).

## Files

| File | Content |
|---|---|
| `memorization_recognition.jsonl` | the 20 full answers, with label |
| `memorization_recognition.csv` | labels per model and schema |
| `env_gen_2026-11-04T104045.json` | environment of the run |

## Reproduce

```bash
python pilot_memorization.py prompts                     # show both schemas
python pilot_memorization.py recognize --allow-mismatch  # on Windows (Ollama), on mains power
```

`--allow-mismatch` is only needed because Ollama was 0.40.13 instead of the configured 0.40.11.
