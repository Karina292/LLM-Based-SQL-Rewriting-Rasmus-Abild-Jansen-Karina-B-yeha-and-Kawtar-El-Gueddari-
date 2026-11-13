WITH filtered_customer AS (
  SELECT
    *
  FROM customer
  WHERE
    c_mktsegment = 'MACHINERY'
), filtered_orders AS (
  SELECT
    *
  FROM orders
  WHERE
    o_orderdate < CAST('1995-03-07' AS DATE)
), filtered_lineitem AS (
  SELECT
    *
  FROM lineitem
  WHERE
    l_shipdate > CAST('1995-03-07' AS DATE)
)
/* using 1792286819 as a seed to the RNG */
SELECT
  l_orderkey,
  SUM(l_extendedprice * (
    1 - l_discount
  )) AS revenue,
  o_orderdate,
  o_shippriority
FROM filtered_customer AS customer, filtered_orders AS orders, filtered_lineitem AS lineitem
WHERE
  c_custkey = o_custkey AND l_orderkey = o_orderkey
GROUP BY
  l_orderkey,
  o_orderdate,
  o_shippriority
ORDER BY
  revenue DESC,
  o_orderdate
LIMIT 10;
