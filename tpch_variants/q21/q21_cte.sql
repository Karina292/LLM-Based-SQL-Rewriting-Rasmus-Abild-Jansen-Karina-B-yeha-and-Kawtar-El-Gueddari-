WITH filtered_l1 AS (
  SELECT
    *
  FROM lineitem
  WHERE
    l_receiptdate > l_commitdate
), filtered_orders AS (
  SELECT
    *
  FROM orders
  WHERE
    o_orderstatus = 'F'
), filtered_nation AS (
  SELECT
    *
  FROM nation
  WHERE
    n_name = 'ALGERIA'
)
/* using 1792286819 as a seed to the RNG */
SELECT
  s_name,
  COUNT(*) AS numwait
FROM supplier, filtered_l1 AS l1, filtered_orders AS orders, filtered_nation AS nation
WHERE
  (
    (
      (
        s_suppkey = l1.l_suppkey AND o_orderkey = l1.l_orderkey
      )
      AND EXISTS(
        SELECT
          *
        FROM lineitem AS l2
        WHERE
          l2.l_orderkey = l1.l_orderkey AND l2.l_suppkey <> l1.l_suppkey
      )
    )
    AND NOT EXISTS(
      SELECT
        *
      FROM lineitem AS l3
      WHERE
        l3.l_orderkey = l1.l_orderkey
        AND l3.l_suppkey <> l1.l_suppkey
        AND l3.l_receiptdate > l3.l_commitdate
    )
  )
  AND s_nationkey = n_nationkey
GROUP BY
  s_name
ORDER BY
  numwait DESC,
  s_name
LIMIT 100;
