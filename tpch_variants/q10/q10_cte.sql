WITH filtered_orders AS (
  SELECT
    *
  FROM orders
  WHERE
    o_orderdate >= CAST('1994-03-01' AS DATE)
    AND o_orderdate < CAST('1994-03-01' AS DATE) + INTERVAL '3 MONTH'
), filtered_lineitem AS (
  SELECT
    *
  FROM lineitem
  WHERE
    l_returnflag = 'R'
)
/* using 1792286819 as a seed to the RNG */
SELECT
  c_custkey,
  c_name,
  SUM(l_extendedprice * (
    1 - l_discount
  )) AS revenue,
  c_acctbal,
  n_name,
  c_address,
  c_phone,
  c_comment
FROM customer, filtered_orders AS orders, filtered_lineitem AS lineitem, nation
WHERE
  (
    c_custkey = o_custkey AND l_orderkey = o_orderkey
  )
  AND c_nationkey = n_nationkey
GROUP BY
  c_custkey,
  c_name,
  c_acctbal,
  c_phone,
  n_name,
  c_address,
  c_comment
ORDER BY
  revenue DESC
LIMIT 20;
