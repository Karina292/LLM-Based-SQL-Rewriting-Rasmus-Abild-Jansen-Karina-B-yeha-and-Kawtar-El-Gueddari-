/* using 1792286819 as a seed to the RNG */
SELECT
  l_orderkey,
  SUM(l_extendedprice * (
    1 - l_discount
  )) AS revenue,
  o_orderdate,
  o_shippriority
FROM (
  SELECT
    *
  FROM customer
  WHERE
    c_mktsegment = 'MACHINERY'
) AS customer, (
  SELECT
    *
  FROM orders
  WHERE
    o_orderdate < CAST('1995-03-07' AS DATE)
) AS orders, (
  SELECT
    *
  FROM lineitem
  WHERE
    l_shipdate > CAST('1995-03-07' AS DATE)
) AS lineitem
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
