/* using 1792286819 as a seed to the RNG */
SELECT
  ps_partkey,
  SUM(ps_supplycost * ps_availqty) AS value
FROM partsupp, supplier, (
  SELECT
    *
  FROM nation
  WHERE
    n_name = 'ETHIOPIA'
) AS nation
WHERE
  ps_suppkey = s_suppkey AND s_nationkey = n_nationkey
GROUP BY
  ps_partkey
HAVING
  SUM(ps_supplycost * ps_availqty) > (
    SELECT
      SUM(ps_supplycost * ps_availqty) * 0.0001000000
    FROM partsupp, supplier, (
      SELECT
        *
      FROM nation
      WHERE
        n_name = 'ETHIOPIA'
    ) AS nation
    WHERE
      ps_suppkey = s_suppkey AND s_nationkey = n_nationkey
  )
ORDER BY
  value DESC;
