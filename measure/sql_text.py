"""
sql_text.py - checks on the SQL *text*, before anything is sent to PostgreSQL.

Role in the pipeline (see measure_one in cli.py):
  1. sql_text.py  -> is the LLM output a single query we can safely run?
                     does it have a top-level ORDER BY?
  2. db.py        -> run it on the database (errors, timeouts)
  3. compare.py   -> does it return the same result as the input query?

Why this is needed:
  - The LLM output is untrusted text. If it contains several statements
    (e.g. "CREATE INDEX ...; SELECT ..."), running it would modify the
    database and bias every later measurement. Such outputs are rejected
    as "multi_statement" without being executed.
  - If the input query has a top-level ORDER BY, row order is part of the
    result and the rewrite must respect it; otherwise order is ignored.

A naive approach (counting ";" or searching "order by" in the raw text)
gives false results when these appear inside a string, a comment or
parentheses, and would wrongly reject correct rewrites. So we first erase
strings and comments, then track the parenthesis depth.

This module never connects to the database.
"""

import re

# Parts of a query whose content must be ignored:
#   '...'      string literal ('' is an escaped quote)
#   "..."      quoted identifier
#   -- ...     line comment
#   /* ... */  block comment (may span several lines, thus we need to use DOTALL)
_IGNORED = re.compile(r"'(?:[^']|'')*'|\"[^\"]*\"|--[^\n]*|/\*.*?\*/", re.DOTALL)


def _strip_strings_and_comments(sql):
    """Replace strings and comments by a space.

    Example: "select 'a;b' from t -- note"  ->  "select   from t  "
    A space (not "") avoids gluing two words together.
    """
    return _IGNORED.sub(" ", sql)


def _depths(sql):
    """Yield (char, depth) for each character, depth = parenthesis level.

    depth 0 = main query; depth >= 1 = inside a subquery, a function call,
    an OVER (...) clause, etc.

    Example: "a(b)c" -> ("a",0) ("(",1) ("b",1) (")",0) ("c",0)
    """
    depth = 0
    for c in _strip_strings_and_comments(sql):
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        yield c, depth


def clean_sql(sql):
    """Remove surrounding whitespace and trailing semicolons.

    Needed because the query is later prefixed with "EXPLAIN (...) ";
    a trailing ";" would end the command too early.
    None (empty generation) is treated as "".

    Example: "  select 1;; "  ->  "select 1"
    """
    s = (sql or "").strip()
    while s.endswith(";"):
        s = s[:-1].rstrip()
    return s


def count_statements(sql):
    """Number of SQL statements in the text.

    Only semicolons at depth 0 (outside strings, comments and parentheses)
    separate statements; empty pieces are not counted.
    Used by measure_one: 0 -> "empty_sql", more than 1 -> "multi_statement".

    Examples:
        "select 1; select 2"   -> 2
        "select ';' from t"    -> 1   (the ; is inside a string)
        ""                     -> 0
    """
    s = clean_sql(sql)
    if not s:
        return 0
    statements, current = [], []
    for c, depth in _depths(s):
        if c == ";" and depth == 0:          # real separator: close current statement
            statements.append("".join(current))
            current = []
        else:
            current.append(c)
    statements.append("".join(current))      # last statement has no ";" after it
    return sum(1 for st in statements if st.strip())


def has_top_level_order_by(sql):
    """True if the main query has an ORDER BY.

    ORDER BY inside parentheses (subquery, OVER (...)) does not count:
    only the outermost one makes row order part of the result.
    Used by compare_results: True -> rows must be in the same order.

    Examples:
        "select a from t order by a"                -> True
        "select rank() over (order by a) from t"    -> False
        "select a from t -- order by a"             -> False (comment)
    """
    # Keep only depth-0 characters, blank out everything in parentheses.
    # ")" is excluded explicitly: its depth is already back to 0 when read.
    top = "".join(c if depth == 0 and c != ")" else " "
                  for c, depth in _depths(clean_sql(sql)))
    return re.search(r"\border\s+by\b", top, re.IGNORECASE) is not None