"""
plans.py - summarizes a query plan to detect whether a rewrite changed it.

PostgreSQL's optimizer may produce the same plan for two different SQL texts
(then the rewrite cannot be faster), or a different plan (different join
algorithm, join order, scans...). Comparing plans by hand for hundreds of
rewrites is not feasible, so each plan is reduced to a signature and a short
hash; equal hashes mean the same plan shape.

The full plans are still saved as JSON in results/plans/ (see io_files.py)
for detailed inspection.
"""

import hashlib


def plan_signature(plan):
    """Turn a plan tree into one line listing its operators.

    `plan` is the "Plan" object of EXPLAIN (FORMAT JSON). The tree is walked
    from the root to the leaves (pre-order). For each node we keep:
        Node Type      e.g. Hash Join, Seq Scan, Sort
        [Join Type]    e.g. [Inner], [Semi], [Anti]
        {Strategy}     aggregation strategy, e.g. {Hashed}, {Sorted}
        (Relation)     table read, e.g. (orders)

    Costs and row estimates are deliberately left out: they vary between
    runs, while the plan *shape* is what tells us the optimizer's strategy.

    Example result:
        "Sort>Aggregate{Hashed}>Hash Join[Semi]>Seq Scan(orders)>Hash>Seq Scan(lineitem)"
    """
    parts = []

    def walk(node):
        label = node.get("Node Type", "?")
        if node.get("Join Type"):
            label += f"[{node['Join Type']}]"
        if node.get("Strategy"):
            label += f"{{{node['Strategy']}}}"
        if node.get("Relation Name"):
            label += f"({node['Relation Name']})"
        parts.append(label)
        for child in node.get("Plans", []) or []:   # recurse into sub-plans
            walk(child)

    walk(plan)
    return ">".join(parts)


def plan_hash(signature):
    """Short, fixed-length code for a signature (first 10 hex chars of SHA-1).

    Easier to store and compare in a CSV than the full signature.
    In measurements.csv: plan_changed = (plan_hash != baseline_plan_hash).
    """
    return hashlib.sha1(signature.encode()).hexdigest()[:10]