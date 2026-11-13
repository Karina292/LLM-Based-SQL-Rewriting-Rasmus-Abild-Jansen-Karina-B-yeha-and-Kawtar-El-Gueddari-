/* using 1792286819 as a seed to the RNG */
SELECT
  o_year,
  SUM(CASE WHEN nation = 'INDONESIA' THEN volume ELSE 0 END) / SUM(volume) AS mkt_share
FROM (
  SELECT
    EXTRACT(YEAR FROM o_orderdate) AS o_year,
    l_extendedprice * (
      1 - l_discount
    ) AS volume,
    n2.n_name AS nation
  FROM (
    SELECT
      *
    FROM part
    WHERE
      p_type = 'SMALL BURNISHED NICKEL'
  ) AS part, supplier, lineitem, (
    SELECT
      *
    FROM orders
    WHERE
      o_orderdate BETWEEN CAST('1995-01-01' AS DATE) AND CAST('1996-12-31' AS DATE)
  ) AS orders, customer, nation AS n1, nation AS n2, (
    SELECT
      *
    FROM region
    WHERE
      r_name = 'ASIA'
  ) AS region
  WHERE
    (
      (
        (
          (
            (
              p_partkey = l_partkey AND s_suppkey = l_suppkey
            ) AND l_orderkey = o_orderkey
          )
          AND o_custkey = c_custkey
        )
        AND c_nationkey = n1.n_nationkey
      )
      AND n1.n_regionkey = r_regionkey
    )
    AND s_nationkey = n2.n_nationkey
) AS all_nations
GROUP BY
  o_year
ORDER BY
  o_year;
