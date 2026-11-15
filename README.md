# LLM-Based SQL Rewriting Experiments

## 1. Project Overview

This project investigates how the syntactic structure of SQL queries affects the ability of Large Language Models (LLMs) to generate correct and optimized SQL rewrites.

The experiments use 15 selected TPC-H queries, each represented in three structurally different forms:

- Explicit ANSI JOINs
- Common Table Expressions (CTEs)
- Nested subqueries

Two language models, Qwen2.5-Coder 7B and Llama 3.1 8B, are evaluated on their ability to rewrite these queries.

This README describes the query preparation, structural transformation, anonymization and verification workflow, as well as the analysis of the experimental results.

## 2. Query Preparation and Processing

This section describes the workflow used to prepare, transform and anonymize the selected TPC-H queries before they are used in the experiments.

All commands must be executed from the project root directory.

### 2.1. Python Environment and Database Configuration

Install the required Python dependencies:

```bash
pip install sqlglot psycopg2-binary pandas numpy matplotlib seaborn
```

To enable PostgreSQL-based query equivalence verification, configure the database connection.

Install the required Python libraries by running the following command from the project root directory:

```bash
cp config/db_config.example.py config/db_config.py
```
These Python libraries are used for SQL parsing and transformation, PostgreSQL database connectivity, experimental data analysis and figure generation.

PostgreSQL must be installed and configured separately if database-based query equivalence verification is required.

Edit `config/db_config.py` with your local PostgreSQL credentials:

```python
DB_CONFIG = {
    "dbname": "YOUR_DATABASE_NAME",
    "user": "YOUR_USERNAME",
    "password": "YOUR_PASSWORD",
    "host": "localhost",
    "port": 5432,
}
```

The local `db_config.py` file is excluded from Git to prevent credentials from being committed. Only the example configuration is included in the repository.

### 2.2. Query Preparation

The selected workload consists of 15 TPC-H queries:

`Q02, Q03, Q04, Q05, Q07, Q08, Q09, Q10, Q11, Q12, Q13, Q17, Q18, Q20 and Q21`.

The script `query_processing/prepare_queries.py` checks that all selected SQL query files are available in `setup/tpch_queries/`.

Run:

```bash
python -m query_processing.prepare_queries
```

The script reports missing queries and confirms whether all 15 selected queries are available. It only checks their presence and does not modify the original SQL files.

### 2.3. SQL Structural Transformations

The script `query_processing/transformations.py` generates three structurally different SQL representations for each selected query:

- Explicit ANSI JOINs
- Common Table Expressions (CTEs)
- Nested subqueries

Run:

```bash
python -m query_processing.transformations
```

The generated variants are saved in `tpch_variants/`, organized into query-specific directories. The script also generates `transformation_report.csv`, which records the transformation status and verification results.

SQL syntax is checked using SQLGlot. When a PostgreSQL connection is available, the script also verifies query equivalence using `EXCEPT ALL` in both directions through `verifier.py`.

If PostgreSQL is unavailable, database-based equivalence verification is skipped and the script continues with SQL syntax and structural checks only.

### 2.4. Query Anonymization

The script `anonymization/anonymize.py` anonymizes the generated SQL variants by replacing table names, column names and selected literal values using predefined mappings.

Run:

```bash
python -m anonymization.anonymize
```

The script reads the generated variants from `tpch_variants/` and saves the anonymized queries in `queries/`.

It also generates `schema_anon.sql`, containing the anonymized PostgreSQL schema definition.

The three structural forms are saved using the following naming convention:

- `qXX_join.sql`
- `qXX_cte.sql`
- `qXX_nested.sql`

### 2.5. Anonymization Verification

After anonymization, run the independent verification script:

```bash
python -m anonymization.check_anonymization
```

This script checks all 45 anonymized query variants and verifies that:

- All expected SQL files exist.
- Each query is syntactically valid according to SQLGlot (PostgreSQL dialect).
- Original TPC-H table names are not present in the anonymized queries.

The script also checks that `schema_anon.sql` exists.

## 3. Measurement (correctness and timing)

Databases: see `setup/README_databases.md` (TPC-H data, anonymized schema, indexes, server settings).

1. Check the pipeline on known cases (uses the original TPC-H names):
   ```sh
   python measure/cli.py selftest --db tpch_sf01     # must end with "SELF-TEST PASSED"
   ```
2. Save the server configuration:
   ```sh
   python measure/cli.py env --db tpch_sf01_anon
   ```
3. Check and time every rewrite against its input query (paired protocol: input and rewrite alternated,
   fresh connection per rewrite, no prepared statements). Always use the queries in `results/queries_used/`:
   ```sh
   python measure/paired.py --db tpch_sf01_anon --queries results/queries_used \
       --generations results/generations.jsonl --out results
   ```
   Repeat with `--db tpch_sf01_idx` and `--db tpch_sf1_anon` (SF 1: Q17 and Q20 excluded, `--timeout-s 120`).
   For Q17 and Q20 at SF 0.1, use `--reps 5 --timeout-s 180` (in our runs, Q17 and Q20 were placed in a
   separate folder and run with these options). The run can be interrupted and restarted: rewrites already
   measured are skipped.
4. Diagnostics of the timing protocol: `python analysis/diag_timing.py --db tpch_sf1_anon`.

Output: `results/measurements.csv` (one row per rewrite and database: verdict, medians, speedup,
plan signature, raw times), `results/baselines.csv`, and the JSON plans in `results/plans/`.

## 4. Experimental Results Analysis

The script `analysis.py` processes the existing experimental measurements stored in `results/measurements.csv`.

Run:

```bash
python analysis.py
```

It generates the paper figures and summary tables in `figures/`, including:

- Correctness by model and query form.
- Correctness by individual query.
- Speedup distribution.
- A LaTeX summary table of the experimental results.

This step analyses the existing measurements and does not generate new LLM rewrites, rerun the experiments or repeat the database performance measurements.

## 5. Reproducibility Notes

The original query files used in the experiments are preserved in `results/queries_used/`. These files must not be replaced with newly generated queries, since different random seeds can produce different query inputs.

The generated transformation variants and anonymized queries are separate preprocessing outputs and should not be confused with the original query files used for the experimental measurements.