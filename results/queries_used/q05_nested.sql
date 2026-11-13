/* using 1433771997 as a seed to the RNG */
SELECT
  col_n_name,
  SUM(col_l_ext_price * (
    1 - col_l_discount
  )) AS revenue
FROM tbl_customers, (
  SELECT
    *
  FROM tbl_orders
  WHERE
    col_o_date >= CAST('1994-01-01' AS DATE)
    AND col_o_date < CAST('1994-01-01' AS DATE) + INTERVAL '1 YEAR'
) AS tbl_orders, tbl_items, tbl_suppliers, tbl_countries, (
  SELECT
    *
  FROM tbl_zones
  WHERE
    col_r_name = 'ZONE_CENTRAL'
) AS tbl_zones
WHERE
  (
    (
      (
        (
          col_c_id = col_o_customer_id AND col_l_order_id = col_o_id
        )
        AND col_l_supplier_id = col_s_id
      )
      AND col_c_country_id = col_s_country_id
    )
    AND col_s_country_id = col_n_id
  )
  AND col_n_zone_id = col_r_id
GROUP BY
  col_n_name
ORDER BY
  revenue DESC;
