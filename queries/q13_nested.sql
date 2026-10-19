SELECT
  c_count,
  COUNT(*) AS custdist
FROM (
  SELECT
    *
  FROM (
    SELECT
      col_c_id,
      COUNT(col_o_id)
    FROM tbl_customers
    LEFT OUTER JOIN tbl_orders
      ON col_c_id = col_o_customer_id AND col_o_notes NOT LIKE '%express%packages%'
    GROUP BY
      col_c_id
  ) AS c_orders(c_custkey, c_count)
) AS sub_data
GROUP BY
  c_count
ORDER BY
  custdist DESC,
  c_count DESC;
