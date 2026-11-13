WITH filtered_tbl_customers AS (
  SELECT
    *
  FROM tbl_customers
  WHERE
    col_c_segment = 'SEGMENT_C'
), filtered_tbl_orders AS (
  SELECT
    *
  FROM tbl_orders
  WHERE
    col_o_date < CAST('1995-03-07' AS DATE)
), filtered_tbl_items AS (
  SELECT
    *
  FROM tbl_items
  WHERE
    col_l_ship_date > CAST('1995-03-07' AS DATE)
)
/* using 1792286819 as a seed to the RNG */
SELECT
  col_l_order_id,
  SUM(col_l_ext_price * (
    1 - col_l_discount
  )) AS revenue,
  col_o_date,
  col_o_ship_level
FROM filtered_tbl_customers AS tbl_customers, filtered_tbl_orders AS tbl_orders, filtered_tbl_items AS tbl_items
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
