"""Anonymization Verification Script (Same layout and reporting style as
transformations.py).
Author: Karina B'yeha
"""

from pathlib import Path
import re
import sqlglot

# ============================================================
# CONFIGURATION & PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
QUERIES_DIR = BASE_DIR / "queries"

SELECTED_QUERIES = [2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 17, 18, 20, 21]
STRUCTURES = ("cte", "join", "nested")

OLD_TABLES = [
    "lineitem",
    "partsupp",
    "orders",
    "customer",
    "supplier",
    "nation",
    "region",
    "part",
]


# ============================================================
# VERIFICATION FUNCTION
# ============================================================


def verify_anonymized_variant(query_id: str, struct: str) -> tuple:
    """Verify that the anonymized file exists, parses in PostgreSQL,
    and has zero TPC-H table leakage.
    """
    file_name = f"{query_id}_{struct}.sql"
    file_path = QUERIES_DIR / file_name

    if not file_path.exists():
        return "MISSING", "File not found", file_name

    sql = file_path.read_text(encoding="utf-8")

    # 1. SQL Syntax validation
    try:
        parsed = sqlglot.parse_one(sql, read="postgres")
        if parsed is None:
            return "FAILED", "SQL parser returned None", file_name
    except Exception as exc:
        return "FAILED", f"Parsing error: {exc}", file_name

    # 2. Leakage check (ignoring SQL comments)
    clean_sql = re.sub(
        r"(--.*$)|(/\*[\s\S]*?\*/)", "", sql, flags=re.MULTILINE
    )
    leaks = [
        tbl
        for tbl in OLD_TABLES
        if re.search(rf"\b{tbl}\b", clean_sql, re.IGNORECASE)
    ]

    if leaks:
        return "LEAKAGE", f"Old table names detected: {leaks}", file_name

    return "SUCCESS", "Valid syntax & Fully anonymized", file_name


# ============================================================
# MAIN PIPELINE
# ============================================================


def main():
    print(f"Target Directory: {QUERIES_DIR}")

    # Check schema_anon.sql existence
    schema_file = QUERIES_DIR / "schema_anon.sql"
    schema_status = (
        "PRESENT"
        if schema_file.exists() and schema_file.stat().st_size > 0
        else "MISSING"
    )
    print(f"Schema DDL (schema_anon.sql): {schema_status}")

    total_checked = 0
    total_success = 0
    total_failed = 0

    for query_num in SELECTED_QUERIES:
        query_id = f"q{query_num:02d}"
        print(f"\n{'=' * 55}\nQUERY {query_id}")

        for struct in STRUCTURES:
            status, details, file_name = verify_anonymized_variant(
                query_id, struct
            )
            total_checked += 1

            if status == "SUCCESS":
                total_success += 1
                result_label = "SUCCESS"
            else:
                total_failed += 1
                result_label = "FAILED"

            print(
                f"{struct.upper():9} | Validation: {status:9} | Outcome: {result_label:8} | File: {file_name}"
            )
            if status != "SUCCESS":
                print(f"          ↳ Details: {details}")

    print(f"\n{'=' * 55}")
    print("ANONYMIZATION CHECK COMPLETED")
    print(f"Total checked: {total_checked}")
    print(f"Successes:     {total_success}")
    print(f"Failures:      {total_failed}")
    print(f"Directory:     {QUERIES_DIR}")


if __name__ == "__main__":
    main()