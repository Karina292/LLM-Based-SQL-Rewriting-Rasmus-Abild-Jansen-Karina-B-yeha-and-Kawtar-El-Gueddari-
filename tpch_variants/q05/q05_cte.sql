WITH filtered_orders AS (
  SELECT
    *
  FROM orders
  WHERE
    o_orderdate >= CAST('1995-01-01' AS DATE)
    AND o_orderdate < CAST('1995-01-01' AS DATE) + INTERVAL '1 YEAR'
), filtered_region AS (
  SELECT
    *
  FROM region
  WHERE
    r_name = 'ASIA'
)
/* using 1792286819 as a seed to the RNG */
SELECT
  n_name,
  SUM(l_extendedprice * (
    1 - l_discount
  )) AS revenue
FROM customer, filtered_orders AS orders, lineitem, supplier, nation, filtered_region AS region
WHERE
  (
    (
      (
        (
          c_custkey = o_custkey AND l_orderkey = o_orderkey
        ) AND l_suppkey = s_suppkey
      )
      AND c_nationkey = s_nationkey
    )
    AND s_nationkey = n_nationkey
  )
  AND n_regionkey = r_regionkey
GROUP BY
  n_name
ORDER BY
  revenue DESC;
