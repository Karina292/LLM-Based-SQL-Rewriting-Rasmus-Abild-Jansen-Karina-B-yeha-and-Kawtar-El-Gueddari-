/* using 1433771997 as a seed to the RNG */
SELECT
  col_l_order_id,
  SUM(col_l_ext_price * (
    1 - col_l_discount
  )) AS revenue,
  col_o_date,
  col_o_ship_level
FROM (
  SELECT
    *
  FROM tbl_customers
  WHERE
    col_c_segment = 'SEGMENT_A'
) AS tbl_customers, (
  SELECT
    *
  FROM tbl_orders
  WHERE
    col_o_date < CAST('1995-03-29' AS DATE)
) AS tbl_orders, (
  SELECT
    *
  FROM tbl_items
  WHERE
    col_l_ship_date > CAST('1995-03-29' AS DATE)
) AS tbl_items
WHERE
  col_c_id = col_o_customer_id AND col_l_order_id = col_o_id
GROUP BY
  col_l_order_id,
  col_o_date,
  col_o_ship_level
ORDER BY
  revenue DESC,
  col_o_date
LIMIT 10;
