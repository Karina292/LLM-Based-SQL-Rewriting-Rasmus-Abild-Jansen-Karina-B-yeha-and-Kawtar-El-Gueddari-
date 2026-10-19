/* using 1433771997 as a seed to the RNG */
SELECT
  col_c_name,
  col_c_id,
  col_o_id,
  col_o_date,
  col_o_total_amount,
  SUM(col_l_qty)
FROM tbl_customers
INNER JOIN tbl_orders
  ON col_c_id = col_o_customer_id
INNER JOIN tbl_items
  ON col_o_id = col_l_order_id
WHERE
  col_o_id IN (
    SELECT
      col_l_order_id
    FROM tbl_items
    GROUP BY
      col_l_order_id
    HAVING
      SUM(col_l_qty) > 313
  )
GROUP BY
  col_c_name,
  col_c_id,
  col_o_id,
  col_o_date,
  col_o_total_amount
ORDER BY
  col_o_total_amount DESC,
  col_o_date
LIMIT 100;
