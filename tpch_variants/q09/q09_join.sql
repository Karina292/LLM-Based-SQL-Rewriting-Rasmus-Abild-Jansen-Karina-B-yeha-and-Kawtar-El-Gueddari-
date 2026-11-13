/* using 1792286819 as a seed to the RNG */
SELECT
  nation,
  o_year,
  SUM(amount) AS sum_profit
FROM (
  SELECT
    n_name AS nation,
    EXTRACT(YEAR FROM o_orderdate) AS o_year,
    l_extendedprice * (
      1 - l_discount
    ) - ps_supplycost * l_quantity AS amount
  FROM part
  INNER JOIN lineitem
    ON p_partkey = l_partkey
  INNER JOIN supplier
    ON s_suppkey = l_suppkey
  INNER JOIN partsupp
    ON ps_suppkey = l_suppkey AND ps_partkey = l_partkey
  INNER JOIN orders
    ON o_orderkey = l_orderkey
  INNER JOIN nation
    ON s_nationkey = n_nationkey
  WHERE
    p_name LIKE '%cream%'
) AS profit
GROUP BY
  nation,
  o_year
ORDER BY
  nation,
  o_year DESC;
