/* using 1792286819 as a seed to the RNG */
SELECT
  col_n_name,
  SUM(col_l_ext_price * (
    1 - col_l_discount
  )) AS revenue
FROM tbl_customers
INNER JOIN tbl_orders
  ON col_c_id = col_o_customer_id
INNER JOIN tbl_items
  ON col_l_order_id = col_o_id
INNER JOIN tbl_suppliers
  ON col_l_supplier_id = col_s_id AND col_c_country_id = col_s_country_id
INNER JOIN tbl_countries
  ON col_s_country_id = col_n_id
INNER JOIN tbl_zones
  ON col_n_zone_id = col_r_id
WHERE
  (
    col_r_name = 'ZONE_EAST' AND col_o_date >= CAST('1995-01-01' AS DATE)
  )
  AND col_o_date < CAST('1995-01-01' AS DATE) + INTERVAL '1 YEAR'
GROUP BY
  col_n_name
ORDER BY
  revenue DESC;
