/* using 1792286819 as a seed to the RNG */
SELECT
  o_orderpriority,
  COUNT(*) AS order_count
FROM (
  SELECT
    *
  FROM orders
  WHERE
    o_orderdate >= CAST('1994-01-01' AS DATE)
    AND o_orderdate < CAST('1994-01-01' AS DATE) + INTERVAL '3 MONTH'
) AS orders
WHERE
  EXISTS(
    SELECT
      *
    FROM (
      SELECT
        *
      FROM lineitem
      WHERE
        l_orderkey = o_orderkey AND l_commitdate < l_receiptdate
    ) AS lineitem
  )
GROUP BY
  o_orderpriority
ORDER BY
  o_orderpriority;
