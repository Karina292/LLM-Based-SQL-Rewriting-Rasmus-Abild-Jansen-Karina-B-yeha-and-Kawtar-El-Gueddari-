WITH filtered_part AS (
  SELECT
    *
  FROM part
  WHERE
    p_brand = 'Brand#41' AND p_container = 'LG BAG'
)
/* using 1792286819 as a seed to the RNG */
SELECT
  SUM(l_extendedprice) / 7.0 AS avg_yearly
FROM lineitem, filtered_part AS part
WHERE
  p_partkey = l_partkey
  AND l_quantity < (
    SELECT
      0.2 * AVG(l_quantity)
    FROM lineitem
    WHERE
      l_partkey = p_partkey
  );
