"""
Workload Preparation
Extracts and normalizes the 15 selected TPC-H queries into tpch_queries/.
Author: Karina B'yeha
"""

from pathlib import Path
import re
import shutil

PROJECT_DIR = Path(__file__).resolve().parent
SOURCE_DIR = PROJECT_DIR / "setup" / "tpch_queries"
OUTPUT_DIR = PROJECT_DIR / "tpch_queries"

# 15 selected TPC-H benchmark queries
SELECTED_QUERIES = [2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 17, 18, 20, 21]

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_query_files(folder: Path) -> dict:
    """Locate SQL query files and index them by query number."""
    query_files = {}
    if not folder.exists():
        return query_files
    for path in folder.rglob("*.sql"):
        match = re.fullmatch(r"q?0*(\d+)\.sql", path.name, re.IGNORECASE)
        if match:
            query_files.setdefault(int(match.group(1)), path)
    return query_files


def main():
    sources = get_query_files(SOURCE_DIR) or get_query_files(OUTPUT_DIR)
    if not sources:
        print("[WARNING] No source SQL files found in setup/tpch_queries.")
        return

    for q_num in SELECTED_QUERIES:
        src = sources.get(q_num)
        if not src:
            print(f"[WARNING] Query {q_num} missing.")
            continue

        dst = OUTPUT_DIR / f"q{q_num:02d}.sql"
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
            print(f"Copied: {src.name} -> {dst.name}")

    print(f"\n[DONE] Prepared 15 benchmark queries in: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
