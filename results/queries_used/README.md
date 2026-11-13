# Queries used in the experiment

These are the exact input queries (anonymized TPC-H, in nested, join and CTE
form, plus `schema_anon.sql`) that `results/generations.jsonl` and
`results/measurements.csv` are based on. They were taken from `queries/` as it
was before commit e80e271.

`queries/` in the repository root now holds a newer version generated with a
different qgen seed, so its parameter values differ from these. Use the files
here to reproduce the reported results.
