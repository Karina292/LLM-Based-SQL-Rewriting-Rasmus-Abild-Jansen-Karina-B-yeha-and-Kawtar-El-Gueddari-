"""
Workload Preparation
Verifies that the 15 selected TPC-H queries exist in setup/tpch_queries/.
Author: Karina B'yeha
"""

from pathlib import Path
import re

PROJECT_DIR = Path(__file__).resolve().parent
QUERY_DIR = PROJECT_DIR / "setup" / "tpch_queries"

# 15 selected TPC-H benchmark queries
SELECTED_QUERIES = [2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 17, 18, 20, 21]


def get_query_files(folder: Path) -> dict:
    """Locate SQL query files and index them by query number."""
    query_files = {}
    if not folder.exists():
        return query_files
    for path in folder.rglob("*.sql"):
        match = re.search(r"(\d+)", path.stem)
        if match:
            query_files.setdefault(int(match.group(1)), path)
    return query_files


def main():
    queries = get_query_files(QUERY_DIR)
    if not queries:
        print(f"[WARNING] No SQL query files found in: {QUERY_DIR}")
        return

    missing = []
    for q_num in SELECTED_QUERIES:
        if q_num in queries:
            print(f"[FOUND] Query {q_num}: {queries[q_num].name}")
        else:
            missing.append(q_num)

    if missing:
        print(f"\n[WARNING] Missing queries: {missing}")
    else:
        print(f"\n[SUCCESS] All 15 benchmark queries verified in: {QUERY_DIR}")


if __name__ == "__main__":
    main()