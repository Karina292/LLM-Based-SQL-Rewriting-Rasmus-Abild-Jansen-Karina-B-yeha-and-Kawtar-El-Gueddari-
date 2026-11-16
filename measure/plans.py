"""
Tells whether a rewrite changed the query plan.

Each plan is reduced to the list of its operators (node, join type,
aggregation, table) and a short hash. Same hash = same plan, so the rewrite
cannot really be faster. The full plans are saved in results/plans/.
"""

import hashlib


def plan_signature(plan):
    """Turn a plan tree into one line listing its operators.

    'plan' is the "Plan" object of EXPLAIN (FORMAT JSON). The tree is walked
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