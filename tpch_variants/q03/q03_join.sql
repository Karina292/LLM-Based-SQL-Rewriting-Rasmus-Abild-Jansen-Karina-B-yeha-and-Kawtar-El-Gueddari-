/* using 1792286819 as a seed to the RNG */
SELECT
  l_orderkey,
  SUM(l_extendedprice * (
    1 - l_discount
  )) AS revenue,
  o_orderdate,
  o_shippriority
FROM customer
INNER JOIN orders
  ON c_custkey = o_custkey
INNER JOIN lineitem
  ON l_orderkey = o_orderkey
WHERE
  (
    c_mktsegment = 'MACHINERY' AND o_orderdate < CAST('1995-03-07' AS DATE)
  )
  AND l_shipdate > CAST('1995-03-07' AS DATE)
GROUP BY
  l_orderkey,
  o_orderdate,
  o_shippriority
ORDER BY
  revenue DESC,
  o_orderdate
LIMIT 10;
