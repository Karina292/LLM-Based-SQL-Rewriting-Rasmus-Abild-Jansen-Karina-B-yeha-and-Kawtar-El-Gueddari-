WITH c_orders AS (
  SELECT
    c_custkey AS c_custkey,
    COUNT(o_orderkey) AS c_count
  FROM customer
  LEFT OUTER JOIN orders
    ON c_custkey = o_custkey AND o_comment NOT LIKE '%special%deposits%'
  GROUP BY
    c_custkey
)
/* using 1792286819 as a seed to the RNG */
SELECT
  c_count,
  COUNT(*) AS custdist
FROM c_orders
GROUP BY
  c_count
ORDER BY
  custdist DESC,
  c_count DESC;
