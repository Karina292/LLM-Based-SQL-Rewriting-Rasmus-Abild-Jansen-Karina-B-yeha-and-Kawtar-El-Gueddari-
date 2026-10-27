SELECT
  col_c_name,
  col_c_id,
  col_o_id,
  col_o_date,
  col_o_total_amount,
  SUM(col_l_qty)
FROM (
  SELECT
    *
  FROM tbl_customers, tbl_orders, tbl_items
  WHERE
    col_o_id IN (
      SELECT
        col_l_order_id
      FROM tbl_items
      GROUP BY
        col_l_order_id
      HAVING
        SUM(col_l_qty) > 300
    )
    AND col_c_id = col_o_customer_id
    AND col_o_id = col_l_order_id
) AS sub_data
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
