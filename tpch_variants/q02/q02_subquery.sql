/* using 1792286819 as a seed to the RNG */
SELECT
  s_acctbal,
  s_name,
  n_name,
  p_partkey,
  p_mfgr,
  s_address,
  s_phone,
  s_comment
FROM (
  SELECT
    *
  FROM part
  WHERE
    p_size = 17 AND p_type LIKE '%NICKEL'
) AS part, supplier, partsupp, nation, (
  SELECT
    *
  FROM region
  WHERE
    r_name = 'AMERICA'
) AS region
WHERE
  (
    (
      (
        p_partkey = ps_partkey AND s_suppkey = ps_suppkey
      )
      AND s_nationkey = n_nationkey
    )
    AND n_regionkey = r_regionkey
  )
  AND ps_supplycost = (
    SELECT
      MIN(ps_supplycost)
    FROM partsupp, supplier, nation, region
    WHERE
      p_partkey = ps_partkey
      AND s_suppkey = ps_suppkey
      AND s_nationkey = n_nationkey
      AND n_regionkey = r_regionkey
      AND r_name = 'AMERICA'
  )
ORDER BY
  s_acctbal DESC,
  n_name,
  s_name,
  p_partkey
LIMIT 100;
