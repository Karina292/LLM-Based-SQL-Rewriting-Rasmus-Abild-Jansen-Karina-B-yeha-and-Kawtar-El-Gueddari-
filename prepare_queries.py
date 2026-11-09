"""Prepare TPC-H query files from an archive or source directory.

Extracts only the 15 queries selected for the benchmark.
"""

from pathlib import Path
import re
import shutil
import zipfile

PROJECT_DIR = Path(__file__).resolve().parent
ZIP_PATH = PROJECT_DIR / "tpch_queries(1).zip"
OUTPUT_DIR = PROJECT_DIR / "tpch_queries"

# 15 selected TPC-H queries for the study
SELECTED_QUERIES = [2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 17, 18, 20, 21]

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def find_query_files(folder):
    """Locate SQL query files named q2.sql, q02.sql, or 2.sql."""
    query_files = {}
    for path in folder.rglob("*.sql"):
        match = re.fullmatch(r"q?0*(\d+)\.sql", path.name, re.IGNORECASE)
        if not match:
            continue
        query_number = int(match.group(1))
        if 1 <= query_number <= 22:
            query_files.setdefault(query_number, path)
    return query_files


# 1. Look for already extracted files
sources = find_query_files(OUTPUT_DIR)

# 2. If not found, attempt extraction from the ZIP archive
if not sources and ZIP_PATH.exists():
    extraction_dir = PROJECT_DIR / "_tpch_extracted"
    extraction_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH) as archive:
        archive.extractall(extraction_dir)
    sources = find_query_files(extraction_dir)

if not sources:
    raise FileNotFoundError(
        "SQL queries not found. Please place tpch_queries(1).zip "
        "or raw SQL files in the project directory."
    )

# 3. Copy only the 15 selected benchmark queries
for i in SELECTED_QUERIES:
    source = sources.get(i)
    if source is None:
        print(f"WARNING: Query {i} not found.")
        continue

    destination = OUTPUT_DIR / f"q{i:02d}.sql"
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)
        print(f"Copied: {source.name} -> {destination.name}")
    else:
        print(f"Already present: {destination.name}")

print(f"\nSelected queries saved to: {OUTPUT_DIR}")