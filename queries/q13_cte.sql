WITH c_tbl_orders AS (
  SELECT
    col_c_id AS c_custkey,
    COUNT(col_o_id) AS c_count
  FROM tbl_customers
  LEFT OUTER JOIN tbl_orders
    ON col_c_id = col_o_customer_id AND col_o_notes NOT LIKE '%special%deposits%'
  GROUP BY
    col_c_id
)
/* using 1792286819 as a seed to the RNG */
SELECT
  c_count,
  COUNT(*) AS custdist
FROM c_tbl_orders
GROUP BY
  c_count
ORDER BY
  custdist DESC,
  c_count DESC;
