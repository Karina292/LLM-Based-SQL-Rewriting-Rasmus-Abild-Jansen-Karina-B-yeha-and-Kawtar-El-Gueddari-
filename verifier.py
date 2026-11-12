"""
SQL Structure and Semantic Equivalence Verification Module.
Author: Karina B'yeha
"""

import sqlglot
from sqlglot import exp


def verify_structure(sql: str, expected_type: str) -> tuple:
    """
    Validate whether the SQL query conforms to the expected structural pattern
    (join, cte, subquery) while rejecting trivial/empty wrappers.
    """
    try:
        ast = sqlglot.parse_one(sql.strip().rstrip(";"), read="postgres")

        if not isinstance(ast, (exp.Select, exp.Union)):
            return False, "Root node is not a SELECT or UNION statement"

        expected = expected_type.lower().strip()

        # ----------------------------------------------------
        # 1. JOIN VERIFICATION
        # ----------------------------------------------------
        if expected == "join":
            joins = list(ast.find_all(exp.Join))
            if not joins:
                return False, "No explicit JOIN keywords found"

            # Check for explicit JOINs having ON or USING conditions
            valid_joins = [
                j
                for j in joins
                if j.args.get("on") is not None
                or j.args.get("using") is not None
                or j.args.get("kind") == "CROSS"
            ]

            if not valid_joins:
                return False, "JOINs present but missing ON/USING conditions"

            return (
                True,
                f"Valid explicit JOIN structure ({len(valid_joins)} join predicates)",
            )

        # ----------------------------------------------------
        # 2. CTE VERIFICATION
        # ----------------------------------------------------
        elif expected == "cte":
            with_clause = ast.args.get("with_")
            if with_clause is None or not with_clause.expressions:
                return False, "No WITH / CTE clause found"

            # Reject trivial wrappers: WITH x AS (full_query) SELECT * FROM x
            if isinstance(ast, exp.Select):
                from_c = ast.args.get("from_")
                exprs = ast.expressions or []
                is_star = len(exprs) == 1 and isinstance(
                    exprs[0], (exp.Star, exp.Column)
                )
                has_no_clauses = not any([
                    ast.args.get("where"),
                    ast.args.get("joins"),
                    ast.args.get("group"),
                    ast.args.get("order"),
                    ast.args.get("having"),
                ])
                if (
                    len(with_clause.expressions) == 1
                    and is_star
                    and has_no_clauses
                ):
                    return (
                        False,
                        "Rejected: Trivial wrapper WITH x AS (...) SELECT * FROM x",
                    )

            return (
                True,
                f"Valid CTE structure ({len(with_clause.expressions)} modular WITH blocks)",
            )

        # ----------------------------------------------------
        # 3. SUBQUERY VERIFICATION
        # ----------------------------------------------------
        elif expected == "subquery":
            # Reject outer trivial wrappers: SELECT * FROM (full_query)
            if isinstance(ast, exp.Select):
                from_c = ast.args.get("from_")
                exprs = ast.expressions or []
                is_star = len(exprs) == 1 and isinstance(
                    exprs[0], (exp.Star, exp.Column)
                )
                has_no_clauses = not any([
                    ast.args.get("where"),
                    ast.args.get("joins"),
                    ast.args.get("group"),
                    ast.args.get("order"),
                    ast.args.get("having"),
                ])
                if (
                    from_c
                    and isinstance(from_c.this, exp.Subquery)
                    and is_star
                    and has_no_clauses
                ):
                    return (
                        False,
                        "Rejected: Trivial outer wrapper SELECT * FROM (...)",
                    )

            # Search for real subqueries across FROM, JOIN, WHERE, and HAVING
            all_selects = list(ast.find_all(exp.Select))
            all_subqueries = list(ast.find_all(exp.Subquery))

            if len(all_subqueries) > 0 or len(all_selects) > 1:
                count = max(len(all_subqueries), len(all_selects) - 1)
                return True, f"Valid Subquery structure ({count} subqueries detected)"

            return False, "No subqueries detected (single-level flat query)"

        return False, f"Unknown structural pattern: {expected_type}"

    except Exception as exc:
        return False, f"SQL parsing error: {exc}"


def verify_equivalence(cursor, original_sql: str, variant_sql: str) -> bool:
    """
    Verify semantic multiset (bag) equivalence between two queries on PostgreSQL
    using symmetric multiset difference (EXCEPT ALL).
    """
    original = original_sql.strip().rstrip(";").strip()
    variant = variant_sql.strip().rstrip(";").strip()

    comparison_sql = f"""
        SELECT NOT EXISTS (
            (
                SELECT *
                FROM ({original}) AS original_result
                EXCEPT ALL
                SELECT *
                FROM ({variant}) AS variant_result
            )
            UNION ALL
            (
                SELECT *
                FROM ({variant}) AS variant_result
                EXCEPT ALL
                SELECT *
                FROM ({original}) AS original_result
            )
        );
    """

    try:
        cursor.execute(comparison_sql)
        row = cursor.fetchone()
        if row is None:
            return None
        return bool(row[0])

    except Exception as exc:
        try:
            cursor.connection.rollback()
        except Exception:
            pass

        print(f"[EQUIVALENCE ERROR] {type(exc).__name__}: {exc}")
        return None