WITH filtered_nation AS (
  SELECT
    *
  FROM nation
  WHERE
    n_name = 'ETHIOPIA'
)
/* using 1792286819 as a seed to the RNG */
SELECT
  ps_partkey,
  SUM(ps_supplycost * ps_availqty) AS value
FROM partsupp, supplier, filtered_nation AS nation
WHERE
  ps_suppkey = s_suppkey AND s_nationkey = n_nationkey
GROUP BY
  ps_partkey
HAVING
  SUM(ps_supplycost * ps_availqty) > (
    SELECT
      SUM(ps_supplycost * ps_availqty) * 0.0001000000
    FROM partsupp, supplier, nation
    WHERE
      ps_suppkey = s_suppkey AND s_nationkey = n_nationkey AND n_name = 'ETHIOPIA'
  )
ORDER BY
  value DESC;
