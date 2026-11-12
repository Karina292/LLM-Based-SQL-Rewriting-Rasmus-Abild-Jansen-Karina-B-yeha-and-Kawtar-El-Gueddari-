WITH filtered_tbl_orders AS (
  SELECT
    *
  FROM tbl_orders
  WHERE
    col_o_date >= CAST('1994-03-01' AS DATE)
    AND col_o_date < CAST('1994-03-01' AS DATE) + INTERVAL '3 MONTH'
), filtered_tbl_items AS (
  SELECT
    *
  FROM tbl_items
  WHERE
    col_l_ret_flag = 'R'
)
/* using 1792286819 as a seed to the RNG */
SELECT
  col_c_id,
  col_c_name,
  SUM(col_l_ext_price * (
    1 - col_l_discount
  )) AS revenue,
  col_c_balance,
  col_n_name,
  col_c_address,
  col_c_phone,
  col_c_notes
FROM tbl_customers, filtered_tbl_orders AS tbl_orders, filtered_tbl_items AS tbl_items, tbl_countries
WHERE
  (
    col_c_id = col_o_customer_id AND col_l_order_id = col_o_id
  )
  AND col_c_country_id = col_n_id
GROUP BY
  col_c_id,
  col_c_name,
  col_c_balance,
  col_c_phone,
  col_n_name,
  col_c_address,
  col_c_notes
ORDER BY
  revenue DESC
LIMIT 20;
